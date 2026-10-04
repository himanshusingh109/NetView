"""
NetView: A Python Tkinter-Based Network Monitoring and Diagnostic System
Main Application Entry Point - Phase 4: Full GUI and Service Integration
"""
import os
import queue
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

# Ensure NetView project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.database import (
    init_db,
    seed_default_hosts_if_empty,
    DEFAULT_DB_PATH,
)
from services.alert_service import AlertService
from services.monitor_service import MonitorService
from gui.dashboard import DashboardTab
from gui.monitor import MonitorTab
from gui.diagnostics import DiagnosticsTab
from gui.history import HistoryTab


class NetViewApp:
    """Main Application Controller initializing the Tkinter root, styling, tabs, and queue loop."""

    def __init__(self, root: tk.Tk, db_path: Optional[str] = None):
        self.root = root
        self.db_path = db_path or DEFAULT_DB_PATH
        self.root.title("NetView - Network Monitoring and Diagnostic System")
        self.root.geometry("1040x720")
        self.root.minsize(900, 600)

        # 1. Initialize SQLite Database & default demo hosts
        init_db(self.db_path)
        seed_default_hosts_if_empty(self.db_path)

        # 2. Thread-safe event queue for non-blocking UI updates
        self.event_queue = queue.Queue()

        # 3. Instantiate Background Services
        self.alert_service = AlertService(
            warning_latency_ms=150.0, critical_latency_ms=300.0
        )
        self.monitor_service = MonitorService(
            event_queue=self.event_queue,
            alert_service=self.alert_service,
            db_path=self.db_path,
        )

        self._configure_styles()
        self._build_layout()

        # 4. Start background monitoring of all active hosts
        self.monitor_service.start_all(active_only=True)

        # 5. Handle clean exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 6. Start non-blocking queue consumer loop (runs strictly on Tkinter main thread)
        self.root.after(50, self.process_queue)

    def _configure_styles(self):
        """Configures clean, consistent styling across TTK widgets."""
        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        if "clam" in available_themes:
            self.style.theme_use("clam")

        self.style.configure(".", font=("Segoe UI", 9))
        self.style.configure("TNotebook", tabposition="n", padding=5)
        self.style.configure(
            "TNotebook.Tab",
            font=("Segoe UI", 10, "bold"),
            padding=(15, 7),
        )
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_layout(self):
        """Constructs the primary Notebook tabs and bottom status bar."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 1. Dashboard Tab
        self.tab_dashboard = DashboardTab(self.notebook, app=self)
        self.notebook.add(self.tab_dashboard, text="  Dashboard  ")

        # 2. Host Monitor Tab
        self.tab_monitor = MonitorTab(self.notebook, app=self)
        self.notebook.add(self.tab_monitor, text="  Host Monitor  ")

        # 3. Diagnostics Tab
        self.tab_diagnostics = DiagnosticsTab(self.notebook, app=self)
        self.notebook.add(self.tab_diagnostics, text="  Diagnostics  ")

        # 4. History & Reports Tab
        self.tab_history = HistoryTab(self.notebook, app=self)
        self.notebook.add(self.tab_history, text="  History & Reports  ")

        # Bottom Status Bar
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(8, 4))
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status = ttk.Label(
            self.status_bar,
            text="Status: Active | Background Worker Queue: Listening",
            font=("Segoe UI", 9),
        )
        self.lbl_status.pack(side=tk.LEFT)

        self.lbl_db_status = ttk.Label(
            self.status_bar,
            text=f"SQLite: {os.path.basename(self.db_path)} (WAL Mode)",
            font=("Segoe UI", 9, "italic"),
            foreground="#2e7d32",
        )
        self.lbl_db_status.pack(side=tk.RIGHT, padx=10)

    def process_queue(self):
        """
        Polls the thread-safe queue every 50ms on the Tkinter main thread.
        Guarantees that background network worker threads never touch Tk widgets directly.
        """
        try:
            # Process up to 25 pending messages per 50ms tick to keep UI crisp and responsive
            count = 0
            while count < 25:
                msg = self.event_queue.get_nowait()
                msg_type = msg.get("type")
                payload = msg.get("payload")

                if msg_type == "TELEMETRY_UPDATE":
                    self.tab_dashboard.on_telemetry(payload)
                    self.tab_monitor.on_telemetry(payload)
                elif msg_type == "ALERT":
                    self.tab_dashboard.on_alert(payload)
                    self.tab_history.refresh_alerts()
                elif msg_type == "NETWORK_PROFILE":
                    self.tab_dashboard.update_network_profile_ui(payload)
                elif msg_type == "PING_DIAGNOSTIC":
                    self.tab_diagnostics.on_ping_result(payload)
                elif msg_type == "DNS_RESULT":
                    lookup_type, data = payload
                    self.tab_diagnostics.on_dns_result(lookup_type, data)
                elif msg_type == "TRACE_HOP":
                    self.tab_diagnostics.on_trace_hop(payload)
                elif msg_type == "TRACE_COMPLETE":
                    self.tab_diagnostics.on_trace_complete(payload)
                elif msg_type == "ECHO_RESULT":
                    self.tab_diagnostics.on_echo_result(payload)
                elif msg_type == "MONITOR_ERROR":
                    err_msg = payload.get("error", "Monitor error")
                    self.lbl_status.config(text=f"Status: Worker Notice - {err_msg}")

                self.event_queue.task_done()
                count += 1
        except queue.Empty:
            pass
        finally:
            # Schedule next queue poll
            self.root.after(50, self.process_queue)

    def on_close(self):
        """Gracefully tears down the application and stops all background workers."""
        try:
            self.lbl_status.config(text="Status: Shutting down background workers...")
            self.root.update_idletasks()

            # 1. Stop all monitor service threads
            if hasattr(self, "monitor_service"):
                self.monitor_service.stop_all(timeout=1.5)

            # 2. Stop echo server if running
            if hasattr(self, "tab_diagnostics") and self.tab_diagnostics.echo_server:
                self.tab_diagnostics.echo_server.stop()
        except Exception:
            pass
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = NetViewApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
