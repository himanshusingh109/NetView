"""
History & Reports Tab: Historical telemetry browser, alert incident logs,
filtering, and CSV/JSON data export using export_service.py.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, Any, List

from database.database import (
    get_all_hosts,
    get_recent_telemetry,
    get_recent_alerts,
)
from services.export_service import (
    export_telemetry_to_csv,
    export_alerts_to_csv,
    export_history_to_json,
)


class HistoryTab(ttk.Frame):
    """History view displaying SQLite logs with filtering and data export facilities."""

    def __init__(self, parent, app=None):
        super().__init__(parent, padding=15)
        self.app = app
        self._host_map: Dict[str, Optional[int]] = {}

        self._build_ui()
        self.refresh_logs()

    def _build_ui(self):
        # 1. Filter Toolbar
        filter_bar = ttk.LabelFrame(self, text="Filter Telemetry Records", padding=10)
        filter_bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_bar, text="Target Node:").pack(side=tk.LEFT, padx=(0, 5))
        self.cb_target = ttk.Combobox(filter_bar, state="readonly", width=22)
        self.cb_target.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(filter_bar, text="Status Filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.cb_status = ttk.Combobox(
            filter_bar,
            values=["ALL", "ONLINE", "HIGH_LATENCY", "OFFLINE"],
            state="readonly",
            width=14,
        )
        self.cb_status.current(0)
        self.cb_status.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Button(filter_bar, text="Apply Filter", command=self.apply_filter).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(filter_bar, text="Clear Filters", command=self.clear_filter).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(filter_bar, text="Refresh Logs", command=self.refresh_logs).pack(side=tk.LEFT)

        # 2. Split Tables: Telemetry History (Top) and Alert Incidents (Bottom)
        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Top: Telemetry Table
        telem_frame = ttk.LabelFrame(paned, text="Historical Latency & Loss Records (telemetry table)", padding=8)
        paned.add(telem_frame, weight=3)

        telem_cols = ("timestamp", "target", "latency", "loss", "status")
        self.tree_telem = ttk.Treeview(telem_frame, columns=telem_cols, show="headings", height=7)
        self.tree_telem.heading("timestamp", text="Timestamp")
        self.tree_telem.heading("target", text="Target Host")
        self.tree_telem.heading("latency", text="Latency (ms)")
        self.tree_telem.heading("loss", text="Packet Loss")
        self.tree_telem.heading("status", text="Status")

        self.tree_telem.column("timestamp", width=160)
        self.tree_telem.column("target", width=160)
        self.tree_telem.column("latency", width=100, anchor=tk.CENTER)
        self.tree_telem.column("loss", width=90, anchor=tk.CENTER)
        self.tree_telem.column("status", width=90, anchor=tk.CENTER)

        telem_scroll = ttk.Scrollbar(telem_frame, orient=tk.VERTICAL, command=self.tree_telem.yview)
        self.tree_telem.configure(yscrollcommand=telem_scroll.set)
        self.tree_telem.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        telem_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom: Alert Incidents Table
        alert_frame = ttk.LabelFrame(paned, text="Triggered Alerts & Threshold Events (alerts table)", padding=8)
        paned.add(alert_frame, weight=2)

        alert_cols = ("timestamp", "target", "severity", "message")
        self.tree_alerts = ttk.Treeview(alert_frame, columns=alert_cols, show="headings", height=5)
        self.tree_alerts.heading("timestamp", text="Trigger Time")
        self.tree_alerts.heading("target", text="Target Host")
        self.tree_alerts.heading("severity", text="Severity")
        self.tree_alerts.heading("message", text="Event Message")

        self.tree_alerts.column("timestamp", width=160)
        self.tree_alerts.column("target", width=140)
        self.tree_alerts.column("severity", width=90, anchor=tk.CENTER)
        self.tree_alerts.column("message", width=420)

        alert_scroll = ttk.Scrollbar(alert_frame, orient=tk.VERTICAL, command=self.tree_alerts.yview)
        self.tree_alerts.configure(yscrollcommand=alert_scroll.set)
        self.tree_alerts.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        alert_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 3. Export Toolbar
        export_bar = ttk.Frame(self)
        export_bar.pack(fill=tk.X)

        ttk.Label(
            export_bar,
            text="File Handling: Export persistent SQLite records to CSV or JSON formats",
            font=("Segoe UI", 9, "italic"),
            foreground="#666666",
        ).pack(side=tk.LEFT)

        ttk.Button(export_bar, text="Export History (JSON)", command=self.handle_export_json).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(export_bar, text="Export Alerts (CSV)", command=self.handle_export_alerts_csv).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(export_bar, text="Export Telemetry (CSV)", command=self.handle_export_telem_csv).pack(side=tk.RIGHT)

    # ---------------- LOG LOADING & FILTERING ----------------

    def refresh_logs(self):
        """Reloads host filter options and re-queries telemetry & alerts from SQLite."""
        db_path = self.app.db_path if self.app else None
        hosts = get_all_hosts(db_path=db_path)

        # Populate host filter combobox
        host_options = ["All Targets"]
        self._host_map = {"All Targets": None}
        for h in hosts:
            opt = f"#{h['id']} - {h['label']}"
            host_options.append(opt)
            self._host_map[opt] = h["id"]

        self.cb_target["values"] = host_options
        if not self.cb_target.get() or self.cb_target.get() not in host_options:
            self.cb_target.current(0)

        self.apply_filter()
        self.refresh_alerts()

    def apply_filter(self):
        """Queries telemetry based on selected host and status filters."""
        db_path = self.app.db_path if self.app else None
        selected_text = self.cb_target.get()
        selected_host_id = self._host_map.get(selected_text)
        status_filter = self.cb_status.get()

        records = get_recent_telemetry(host_id=selected_host_id, limit=200, db_path=db_path)

        self.tree_telem.delete(*self.tree_telem.get_children())
        for r in records:
            st = r["status"]
            if status_filter != "ALL" and st != status_filter:
                continue

            target_display = f"{r.get('host_label', '')} ({r.get('ip_address', '')})"
            lat = f"{r['latency_ms']} ms" if r["latency_ms"] is not None else "--"
            loss = f"{r.get('packet_loss', 0.0)}%"

            self.tree_telem.insert(
                "", tk.END,
                values=(r["timestamp"], target_display, lat, loss, st)
            )

    def clear_filter(self):
        """Resets filters to default (all targets, all statuses)."""
        self.cb_target.current(0)
        self.cb_status.current(0)
        self.apply_filter()

    def refresh_alerts(self):
        """Loads alerts from SQLite into the alerts table."""
        db_path = self.app.db_path if self.app else None
        alerts = get_recent_alerts(limit=100, db_path=db_path)
        self.tree_alerts.delete(*self.tree_alerts.get_children())
        for a in alerts:
            target_display = f"{a.get('host_label', '')} ({a.get('ip_address', '')})"
            self.tree_alerts.insert(
                "", tk.END,
                values=(a["timestamp"], target_display, a["severity"], a["message"])
            )

    # ---------------- EXPORT HANDLERS ----------------

    def handle_export_telem_csv(self):
        """Prompts save dialog and exports telemetry records to CSV."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile="netview_telemetry_export.csv",
            title="Export Telemetry Records to CSV",
        )
        if not filepath:
            return

        db_path = self.app.db_path if self.app else None
        res = export_telemetry_to_csv(filepath=filepath, db_path=db_path)
        if res["success"]:
            messagebox.showinfo(
                "Export Succeeded",
                f"Successfully exported {res['rows_exported']} telemetry records to:\n{filepath}",
            )
        else:
            messagebox.showerror("Export Failed", res.get("error", "Unknown error"))

    def handle_export_alerts_csv(self):
        """Prompts save dialog and exports alert events to CSV."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile="netview_alerts_export.csv",
            title="Export Alert Records to CSV",
        )
        if not filepath:
            return

        db_path = self.app.db_path if self.app else None
        res = export_alerts_to_csv(filepath=filepath, db_path=db_path)
        if res["success"]:
            messagebox.showinfo(
                "Export Succeeded",
                f"Successfully exported {res['rows_exported']} alert incidents to:\n{filepath}",
            )
        else:
            messagebox.showerror("Export Failed", res.get("error", "Unknown error"))

    def handle_export_json(self):
        """Prompts save dialog and exports comprehensive history to JSON."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile="netview_history_export.json",
            title="Export System History to JSON",
        )
        if not filepath:
            return

        db_path = self.app.db_path if self.app else None
        res = export_history_to_json(filepath=filepath, db_path=db_path)
        if res["success"]:
            messagebox.showinfo(
                "Export Succeeded",
                f"Successfully exported {res['rows_exported']} items to JSON file:\n{filepath}",
            )
        else:
            messagebox.showerror("Export Failed", res.get("error", "Unknown error"))
