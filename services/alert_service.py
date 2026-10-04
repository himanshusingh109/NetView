"""
Alert Evaluation Service for NetView.
Evaluates telemetry against configured thresholds, prevents duplicate alert spamming
using state transition tracking, and records alerts in SQLite.
"""
from typing import Dict, Any, Optional
from database.database import add_alert


class AlertService:
    """Evaluates telemetry checks against latency and reachability thresholds."""

    def __init__(
        self,
        warning_latency_ms: float = 150.0,
        critical_latency_ms: float = 300.0,
    ):
        self.warning_latency_ms = warning_latency_ms
        self.critical_latency_ms = critical_latency_ms
        # Tracks the last alerted state per host_id to avoid redundant alerts on every cycle
        self._last_state: Dict[int, str] = {}

    def evaluate(
        self,
        host_id: int,
        host_label: str,
        ip_address: str,
        telemetry: Dict[str, Any],
        db_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates a telemetry check result for a given host.
        Returns an alert dictionary if a new alert condition was triggered, otherwise None.
        """
        is_online = telemetry.get("success", False)
        latency_ms = telemetry.get("latency_ms")
        prev_state = self._last_state.get(host_id, "NORMAL")
        current_state = "NORMAL"
        alert_event = None

        if not is_online:
            current_state = "OFFLINE"
            # Only trigger alert if host was not already in OFFLINE state
            if prev_state != "OFFLINE":
                msg = f"Host {host_label} ({ip_address}) is OFFLINE: {telemetry.get('error', 'Unreachable')}"
                alert_id = add_alert(host_id, "CRITICAL", msg, db_path=db_path)
                alert_event = {
                    "alert_id": alert_id,
                    "host_id": host_id,
                    "host_label": host_label,
                    "severity": "CRITICAL",
                    "message": msg,
                }
        else:
            # Host is online - check latency thresholds
            if latency_ms is not None:
                if latency_ms >= self.critical_latency_ms:
                    current_state = "CRITICAL_LATENCY"
                    if prev_state != "CRITICAL_LATENCY":
                        msg = (
                            f"Host {host_label} ({ip_address}) latency CRITICAL: "
                            f"{latency_ms}ms (threshold: {self.critical_latency_ms}ms)"
                        )
                        alert_id = add_alert(host_id, "CRITICAL", msg, db_path=db_path)
                        alert_event = {
                            "alert_id": alert_id,
                            "host_id": host_id,
                            "host_label": host_label,
                            "severity": "CRITICAL",
                            "message": msg,
                        }
                elif latency_ms >= self.warning_latency_ms:
                    current_state = "WARNING_LATENCY"
                    if prev_state != "WARNING_LATENCY" and prev_state != "CRITICAL_LATENCY":
                        msg = (
                            f"Host {host_label} ({ip_address}) latency HIGH: "
                            f"{latency_ms}ms (threshold: {self.warning_latency_ms}ms)"
                        )
                        alert_id = add_alert(host_id, "WARNING", msg, db_path=db_path)
                        alert_event = {
                            "alert_id": alert_id,
                            "host_id": host_id,
                            "host_label": host_label,
                            "severity": "WARNING",
                            "message": msg,
                        }
                else:
                    current_state = "NORMAL"
                    # If previously in an alert state, generate a recovery notice
                    if prev_state in ("OFFLINE", "CRITICAL_LATENCY", "WARNING_LATENCY"):
                        msg = f"Host {host_label} ({ip_address}) recovered to normal latency: {latency_ms}ms"
                        alert_id = add_alert(host_id, "INFO", msg, db_path=db_path)
                        alert_event = {
                            "alert_id": alert_id,
                            "host_id": host_id,
                            "host_label": host_label,
                            "severity": "INFO",
                            "message": msg,
                        }

        self._last_state[host_id] = current_state
        return alert_event

    def reset_state(self, host_id: int):
        """Clears state tracking for a specific host."""
        self._last_state.pop(host_id, None)

    def clear_all(self):
        """Clears all tracked state."""
        self._last_state.clear()
