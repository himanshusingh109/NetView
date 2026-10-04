"""
Background Monitor Service for NetView.
Manages per-host background worker threads using threading.Thread (daemon=True),
periodically invokes network.ping, persists telemetry into SQLite, evaluates alerts,
and emits structured events through queue.Queue.
"""
import queue
import threading
import time
from typing import Dict, Any, Optional

from database.database import (
    get_all_hosts,
    get_host_by_id,
    add_telemetry,
)
from network.ping import ping_host
from services.alert_service import AlertService


class MonitorService:
    """
    Orchestrates multithreaded network monitoring without blocking the main/UI thread.
    Each host is monitored on its own independent worker daemon thread.
    """

    def __init__(
        self,
        event_queue: Optional[queue.Queue] = None,
        alert_service: Optional[AlertService] = None,
        db_path: Optional[str] = None,
    ):
        self.event_queue = event_queue or queue.Queue()
        self.alert_service = alert_service or AlertService()
        self.db_path = db_path

        # Thread management structures
        self._lock = threading.Lock()
        self._workers: Dict[int, threading.Thread] = {}
        self._stop_events: Dict[int, threading.Event] = {}
        self._paused_hosts: Dict[int, bool] = {}
        self._global_stop = threading.Event()

    def start_host(self, host: Dict[str, Any]) -> bool:
        """
        Starts a monitoring worker thread for a specific host dictionary.
        Guarantees no duplicate worker is created if one is already running for this host.
        """
        host_id = host["id"]

        with self._lock:
            # Check if a worker for this host is already alive
            if host_id in self._workers:
                worker = self._workers[host_id]
                if worker.is_alive():
                    # Worker is already actively running; avoid duplicate
                    return False

            # Create dedicated stop event for this host worker
            stop_event = threading.Event()
            self._stop_events[host_id] = stop_event
            self._paused_hosts[host_id] = False

            worker = threading.Thread(
                target=self._worker_loop,
                args=(host_id, stop_event),
                name=f"MonitorWorker-Host-{host_id}",
                daemon=True,
            )
            self._workers[host_id] = worker
            worker.start()
            return True

    def start_all(self, active_only: bool = True):
        """Starts monitoring workers for all hosts stored in SQLite."""
        self._global_stop.clear()
        hosts = get_all_hosts(active_only=active_only, db_path=self.db_path)
        for host in hosts:
            self.start_host(host)

    def _worker_loop(self, host_id: int, stop_event: threading.Event):
        """
        Per-host worker routine executing in its own daemon thread.
        Pings target host according to check_interval, saves telemetry,
        checks alerts, and notifies via event_queue.
        """
        while not stop_event.is_set() and not self._global_stop.is_set():
            try:
                # 1. Fetch latest host info from SQLite
                host = get_host_by_id(host_id, db_path=self.db_path)
                if not host:
                    # Host was deleted from database, terminate thread
                    break

                interval = max(1, host.get("check_interval", 5))

                # 2. Check if paused
                with self._lock:
                    is_paused = self._paused_hosts.get(host_id, False)

                if is_paused:
                    # Sleep in small slices so stop_event can interrupt quickly
                    stop_event.wait(timeout=1.0)
                    continue

                target = host["ip_address"]
                label = host["label"]

                # 3. Perform network ping (safe subprocess ICMP)
                ping_res = ping_host(target=target, count=1, timeout_ms=1500)

                if stop_event.is_set() or self._global_stop.is_set():
                    break

                # 4. Save telemetry to SQLite
                latency_ms = ping_res.get("latency_ms")
                status = ping_res.get("status", "OFFLINE")
                packet_loss = ping_res.get("packet_loss_pct", 100.0)

                add_telemetry(
                    host_id=host_id,
                    latency_ms=latency_ms,
                    status=status,
                    packet_loss=packet_loss,
                    db_path=self.db_path,
                )

                # 5. Evaluate Alerts
                alert_event = self.alert_service.evaluate(
                    host_id=host_id,
                    host_label=label,
                    ip_address=target,
                    telemetry=ping_res,
                    db_path=self.db_path,
                )

                if alert_event:
                    self.event_queue.put({"type": "ALERT", "payload": alert_event})

                # 6. Put telemetry event into thread-safe Queue
                event_data = {
                    "type": "TELEMETRY_UPDATE",
                    "payload": {
                        "host_id": host_id,
                        "label": label,
                        "ip_address": target,
                        "latency_ms": latency_ms,
                        "status": status,
                        "packet_loss": packet_loss,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                }
                self.event_queue.put(event_data)

                # 7. Interruptible sleep for the check interval
                stop_event.wait(timeout=float(interval))

            except Exception as e:
                # Log exception to queue and retry after brief delay without crashing thread
                try:
                    self.event_queue.put({
                        "type": "MONITOR_ERROR",
                        "payload": {"host_id": host_id, "error": str(e)},
                    })
                except Exception:
                    pass
                stop_event.wait(timeout=3.0)

    def pause_host(self, host_id: int):
        """Pauses polling for a given host without destroying its worker thread."""
        with self._lock:
            self._paused_hosts[host_id] = True

    def resume_host(self, host_id: int):
        """Resumes polling for a previously paused host."""
        with self._lock:
            self._paused_hosts[host_id] = False

    def is_paused(self, host_id: int) -> bool:
        """Returns True if host is paused."""
        with self._lock:
            return self._paused_hosts.get(host_id, False)

    def is_host_running(self, host_id: int) -> bool:
        """Returns True if worker thread for host exists and is alive."""
        with self._lock:
            worker = self._workers.get(host_id)
            return bool(worker and worker.is_alive())

    def stop_host(self, host_id: int, timeout: float = 2.0):
        """Stops and terminates a specific host's monitoring thread."""
        with self._lock:
            stop_event = self._stop_events.pop(host_id, None)
            worker = self._workers.pop(host_id, None)
            self._paused_hosts.pop(host_id, None)

        if stop_event:
            stop_event.set()
        if worker and worker.is_alive():
            worker.join(timeout=timeout)

    def stop_all(self, timeout: float = 2.0):
        """Gracefully terminates all active monitoring worker threads."""
        self._global_stop.set()

        with self._lock:
            for stop_event in self._stop_events.values():
                stop_event.set()
            workers = list(self._workers.values())
            self._workers.clear()
            self._stop_events.clear()
            self._paused_hosts.clear()

        # Join threads outside the lock
        for worker in workers:
            if worker.is_alive():
                worker.join(timeout=timeout)

    @property
    def active_worker_count(self) -> int:
        """Returns the number of currently alive worker threads."""
        with self._lock:
            return sum(1 for w in self._workers.values() if w.is_alive())
