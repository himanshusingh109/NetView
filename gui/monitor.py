"""
Host Monitor Tab: Target node management, live latency Canvas waveform,
statistics, and MonitorService controls (Start, Pause, Resume, Stop, Remove).
"""
import collections
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional

from database.database import (
    get_all_hosts,
    add_host,
    delete_host,
    update_host_status,
    get_recent_telemetry,
)
from network.ping import ping_host


class MonitorTab(ttk.Frame):
    """Host Monitor view managing targets and rendering live latency telemetry on Canvas."""

    def __init__(self, parent, app=None):
        super().__init__(parent, padding=15)
        self.app = app

        # Rolling latency buffers for each host: host_id -> deque(maxlen=40) of float
        self.latency_history: Dict[int, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=40)
        )
        self.selected_host_id: Optional[int] = None

        self._build_ui()
        self.refresh_host_list()

    def _build_ui(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ----------------- LEFT PANEL: HOST TARGET MANAGEMENT -----------------
        left_frame = ttk.Frame(paned, padding=5)
        paned.add(left_frame, weight=1)

        # Add Host Form Card
        form_card = ttk.LabelFrame(left_frame, text="Add Monitored Target", padding=12)
        form_card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(form_card, text="IP / Domain:").grid(
            row=0, column=0, sticky=tk.W, pady=3, padx=(0, 5)
        )
        self.entry_target = ttk.Entry(form_card, width=22)
        self.entry_target.grid(row=0, column=1, sticky=tk.EW, pady=3)

        ttk.Label(form_card, text="Friendly Label:").grid(
            row=1, column=0, sticky=tk.W, pady=3, padx=(0, 5)
        )
        self.entry_label = ttk.Entry(form_card, width=22)
        self.entry_label.grid(row=1, column=1, sticky=tk.EW, pady=3)

        ttk.Label(form_card, text="Interval (sec):").grid(
            row=2, column=0, sticky=tk.W, pady=3, padx=(0, 5)
        )
        self.entry_interval = ttk.Spinbox(form_card, from_=1, to=60, width=8)
        self.entry_interval.grid(row=2, column=1, sticky=tk.W, pady=3)
        self.entry_interval.set("5")

        btn_add = ttk.Button(form_card, text="Add Target Host", command=self.handle_add_host)
        btn_add.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))

        # Host Table Card
        table_card = ttk.LabelFrame(left_frame, text="Monitored Targets", padding=8)
        table_card.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "label", "ip", "status", "latency", "interval", "active")
        self.tree_hosts = ttk.Treeview(table_card, columns=cols, show="headings", height=8)
        self.tree_hosts.heading("id", text="#")
        self.tree_hosts.heading("label", text="Label")
        self.tree_hosts.heading("ip", text="Target")
        self.tree_hosts.heading("status", text="Status")
        self.tree_hosts.heading("latency", text="Latency")
        self.tree_hosts.heading("interval", text="Interval")
        self.tree_hosts.heading("active", text="Active")

        self.tree_hosts.column("id", width=30, anchor=tk.CENTER, stretch=False)
        self.tree_hosts.column("label", width=110, stretch=True)
        self.tree_hosts.column("ip", width=110, stretch=True)
        self.tree_hosts.column("status", width=75, anchor=tk.CENTER, stretch=False)
        self.tree_hosts.column("latency", width=75, anchor=tk.CENTER, stretch=False)
        self.tree_hosts.column("interval", width=55, anchor=tk.CENTER, stretch=False)
        self.tree_hosts.column("active", width=55, anchor=tk.CENTER, stretch=False)

        tree_scroll = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self.tree_hosts.yview)
        self.tree_hosts.configure(yscrollcommand=tree_scroll.set)

        self.tree_hosts.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_hosts.bind("<<TreeviewSelect>>", self._on_host_selected)

        # Action Buttons Row
        actions_bar = ttk.Frame(left_frame)
        actions_bar.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(actions_bar, text="Start", width=7, command=self.handle_start_selected).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(actions_bar, text="Pause", width=7, command=self.handle_pause_selected).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(actions_bar, text="Resume", width=8, command=self.handle_resume_selected).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(actions_bar, text="Stop", width=7, command=self.handle_stop_selected).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(actions_bar, text="Remove", width=8, command=self.handle_remove_selected).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(actions_bar, text="Ping Now", width=9, command=self.handle_ping_now).pack(side=tk.LEFT)

        # ----------------- RIGHT PANEL: TELEMETRY GRAPH -----------------
        right_frame = ttk.Frame(paned, padding=5)
        paned.add(right_frame, weight=1)

        graph_card = ttk.LabelFrame(right_frame, text="Live Latency Waveform", padding=12)
        graph_card.pack(fill=tk.BOTH, expand=True)

        # Top control bar for graph
        graph_ctrl = ttk.Frame(graph_card)
        graph_ctrl.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(graph_ctrl, text="Active Target:").pack(side=tk.LEFT, padx=(0, 8))
        self.target_selector = ttk.Combobox(
            graph_ctrl,
            state="readonly",
            width=28,
        )
        self.target_selector.pack(side=tk.LEFT)
        self.target_selector.bind("<<ComboboxSelected>>", self._on_combobox_selected)

        # Statistics badges
        self.stats_label = ttk.Label(
            graph_card,
            text="Min: -- | Avg: -- | Max: -- | Status: STANDBY",
            font=("Segoe UI", 9, "bold"),
            foreground="#007acc",
        )
        self.stats_label.pack(anchor=tk.W, pady=(0, 6))

        # Canvas for plotting live waveform
        self.canvas = tk.Canvas(graph_card, bg="#181818", highlightthickness=0, height=270)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw_graph())

    # ---------------- HOST MANAGEMENT ACTIONS ----------------

    def refresh_host_list(self):
        """Reloads hosts from SQLite, updates table and target selector."""
        db_path = self.app.db_path if self.app else None
        hosts = get_all_hosts(db_path=db_path)

        # Retain current selection if possible
        cur_sel = self.tree_hosts.selection()
        sel_id = int(cur_sel[0]) if cur_sel else self.selected_host_id

        self.tree_hosts.delete(*self.tree_hosts.get_children())
        combo_values = []
        target_map = {}

        for h in hosts:
            hid = h["id"]
            label = h["label"]
            ip = h["ip_address"]
            interval = f"{h['check_interval']}s"
            is_act = "Yes" if h["is_active"] else "Paused"

            # Check if telemetry is in buffer
            hist = self.latency_history[hid]
            latest_ms = f"{hist[-1]} ms" if len(hist) > 0 and hist[-1] is not None else "--"

            # Determine monitoring state
            if self.app and hasattr(self.app, "monitor_service"):
                is_running = self.app.monitor_service.is_host_running(hid)
                is_paused = self.app.monitor_service.is_paused(hid)
                if is_paused:
                    status = "PAUSED"
                elif is_running:
                    status = "ONLINE" if latest_ms != "--" else "MONITORING"
                else:
                    status = "STOPPED"
            else:
                status = "STANDBY"

            self.tree_hosts.insert(
                "", tk.END, iid=str(hid),
                values=(hid, label, ip, status, latest_ms, interval, is_act)
            )

            combo_text = f"#{hid} - {label} ({ip})"
            combo_values.append(combo_text)
            target_map[combo_text] = hid

        self._target_map = target_map
        self.target_selector["values"] = combo_values

        if hosts:
            if sel_id and str(sel_id) in self.tree_hosts.get_children():
                self.selected_host_id = sel_id
                self.tree_hosts.selection_set(str(sel_id))
            else:
                first_id = hosts[0]["id"]
                self.selected_host_id = first_id
                self.tree_hosts.selection_set(str(first_id))

            # Sync combobox
            for text, hid in target_map.items():
                if hid == self.selected_host_id:
                    self.target_selector.set(text)
                    break
        else:
            self.selected_host_id = None
            self.target_selector.set("")

        self.redraw_graph()

    def handle_add_host(self):
        """Validates inputs, saves to SQLite, starts monitoring worker."""
        target = self.entry_target.get().strip()
        label = self.entry_label.get().strip()
        interval_str = self.entry_interval.get().strip()

        if not target:
            messagebox.showwarning("Input Error", "Please provide a valid IP address or domain name.")
            return
        if not label:
            label = target
        try:
            interval = int(interval_str)
            if interval < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Input Error", "Check interval must be a positive integer (e.g. 5).")
            return

        db_path = self.app.db_path if self.app else None
        try:
            hid = add_host(target, label, check_interval=interval, db_path=db_path)
            self.entry_target.delete(0, tk.END)
            self.entry_label.delete(0, tk.END)

            # Start monitoring worker if service is available
            if self.app and hasattr(self.app, "monitor_service"):
                host_dict = {
                    "id": hid,
                    "ip_address": target,
                    "label": label,
                    "check_interval": interval,
                    "is_active": 1,
                }
                self.app.monitor_service.start_host(host_dict)

            self.refresh_host_list()
            if self.app and hasattr(self.app, "tab_dashboard"):
                self.app.tab_dashboard.refresh_data()

        except Exception as e:
            messagebox.showerror("Database Error", f"Could not add host: {str(e)}")

    def _get_selected_id(self) -> Optional[int]:
        sel = self.tree_hosts.selection()
        return int(sel[0]) if sel else None

    def handle_start_selected(self):
        hid = self._get_selected_id()
        if not hid:
            messagebox.showinfo("Selection Required", "Please select a host from the table.")
            return

        db_path = self.app.db_path if self.app else None
        if self.app and hasattr(self.app, "monitor_service"):
            from database.database import get_host_by_id
            host = get_host_by_id(hid, db_path=db_path)
            if host:
                self.app.monitor_service.resume_host(hid)
                self.app.monitor_service.start_host(host)
                update_host_status(hid, 1, db_path=db_path)
                self.refresh_host_list()

    def handle_pause_selected(self):
        hid = self._get_selected_id()
        if not hid:
            messagebox.showinfo("Selection Required", "Please select a host from the table.")
            return
        if self.app and hasattr(self.app, "monitor_service"):
            self.app.monitor_service.pause_host(hid)
            self.refresh_host_list()

    def handle_resume_selected(self):
        hid = self._get_selected_id()
        if not hid:
            messagebox.showinfo("Selection Required", "Please select a host from the table.")
            return
        if self.app and hasattr(self.app, "monitor_service"):
            self.app.monitor_service.resume_host(hid)
            self.refresh_host_list()

    def handle_stop_selected(self):
        hid = self._get_selected_id()
        if not hid:
            messagebox.showinfo("Selection Required", "Please select a host from the table.")
            return
        if self.app and hasattr(self.app, "monitor_service"):
            self.app.monitor_service.stop_host(hid)
            self.refresh_host_list()

    def handle_remove_selected(self):
        hid = self._get_selected_id()
        if not hid:
            messagebox.showinfo("Selection Required", "Please select a host from the table to remove.")
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete host #{hid} and all its telemetry history?",
        )
        if not confirm:
            return

        db_path = self.app.db_path if self.app else None
        # Stop worker first
        if self.app and hasattr(self.app, "monitor_service"):
            self.app.monitor_service.stop_host(hid)

        delete_host(hid, db_path=db_path)
        self.latency_history.pop(hid, None)
        self.refresh_host_list()
        if self.app and hasattr(self.app, "tab_dashboard"):
            self.app.tab_dashboard.refresh_data()

    def handle_ping_now(self):
        """Triggers an immediate on-demand probe in a background thread."""
        hid = self._get_selected_id()
        if not hid:
            messagebox.showinfo("Selection Required", "Please select a host from the table to ping.")
            return

        vals = self.tree_hosts.item(str(hid), "values")
        target = vals[2]
        label = vals[1]

        def worker():
            res = ping_host(target, count=1, timeout_ms=1500)
            if self.app and hasattr(self.app, "event_queue"):
                self.app.event_queue.put({
                    "type": "TELEMETRY_UPDATE",
                    "payload": {
                        "host_id": hid,
                        "label": label,
                        "ip_address": target,
                        "latency_ms": res.get("latency_ms"),
                        "status": res.get("status", "OFFLINE"),
                        "packet_loss": res.get("packet_loss_pct", 100.0),
                        "timestamp": "Now",
                    }
                })

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- GRAPH & TELEMETRY UPDATES ----------------

    def _on_host_selected(self, event):
        hid = self._get_selected_id()
        if hid and hid != self.selected_host_id:
            self.selected_host_id = hid
            for text, h_id in getattr(self, "_target_map", {}).items():
                if h_id == hid:
                    self.target_selector.set(text)
                    break
            self.redraw_graph()

    def _on_combobox_selected(self, event):
        val = self.target_selector.get()
        hid = getattr(self, "_target_map", {}).get(val)
        if hid:
            self.selected_host_id = hid
            if str(hid) in self.tree_hosts.get_children():
                self.tree_hosts.selection_set(str(hid))
            self.redraw_graph()

    def on_telemetry(self, payload: Dict[str, Any]):
        """Called on main thread when a new telemetry check arrives."""
        hid = payload["host_id"]
        lat = payload.get("latency_ms")
        st = payload.get("status", "OFFLINE")

        # Append to host latency history buffer
        self.latency_history[hid].append(lat)

        # Update host table row
        if self.tree_hosts.exists(str(hid)):
            current = list(self.tree_hosts.item(str(hid), "values"))
            current[3] = st
            current[4] = f"{lat} ms" if lat is not None else "--"
            self.tree_hosts.item(str(hid), values=current)

        # If this is the currently selected host, redraw the graph!
        if hid == self.selected_host_id:
            self.redraw_graph()

    def redraw_graph(self):
        """Draws the dynamic line chart on the Canvas based on real latency data."""
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width <= 10 or height <= 10:
            width, height = 450, 260

        padding_left = 50
        padding_right = 20
        padding_top = 25
        padding_bottom = 30

        plot_w = width - padding_left - padding_right
        plot_h = height - padding_top - padding_bottom

        if not self.selected_host_id:
            self.canvas.create_text(
                width // 2, height // 2,
                text="No host selected. Add or select a host to monitor.",
                fill="#888888", font=("Segoe UI", 10, "italic"),
            )
            self.stats_label.config(text="Min: -- | Avg: -- | Max: -- | Status: NONE")
            return

        data_points = list(self.latency_history[self.selected_host_id])
        valid_points = [p for p in data_points if p is not None]

        # Calculate statistics
        if valid_points:
            min_lat = min(valid_points)
            max_lat = max(valid_points)
            avg_lat = round(sum(valid_points) / len(valid_points), 1)
            cur_lat = valid_points[-1]
            st = "ONLINE" if cur_lat <= 150 else ("HIGH_LATENCY" if cur_lat <= 300 else "CRITICAL")
            self.stats_label.config(
                text=f"Min: {min_lat} ms | Avg: {avg_lat} ms | Max: {max_lat} ms | Latest: {cur_lat} ms ({st})"
            )
        else:
            self.stats_label.config(text="Min: -- | Avg: -- | Max: -- | Status: WAITING FOR TELEMETRY")

        # Determine Y scale
        max_y = max(valid_points) if valid_points else 100.0
        max_y = max(max_y * 1.25, 40.0)

        # Draw Gridlines and Y Labels
        num_y_ticks = 4
        for i in range(num_y_ticks + 1):
            val = round((max_y / num_y_ticks) * i)
            y_pos = padding_top + plot_h - (i * (plot_h / num_y_ticks))
            self.canvas.create_line(
                padding_left, y_pos, padding_left + plot_w, y_pos,
                fill="#2c2c2c", dash=(2, 4)
            )
            self.canvas.create_text(
                padding_left - 8, y_pos, text=f"{val}ms",
                fill="#777777", font=("Segoe UI", 8), anchor=tk.E
            )

        # Draw X Axis Baseline
        self.canvas.create_line(
            padding_left, padding_top + plot_h,
            padding_left + plot_w, padding_top + plot_h,
            fill="#555555"
        )
        self.canvas.create_text(
            padding_left + plot_w // 2, height - 10,
            text="Recent Polling Samples ->",
            fill="#666666", font=("Segoe UI", 8)
        )

        if not data_points:
            self.canvas.create_text(
                padding_left + plot_w // 2, padding_top + plot_h // 2,
                text="Waiting for first telemetry ping...",
                fill="#666666", font=("Segoe UI", 9, "italic")
            )
            return

        # Plot Data Line
        n_points = len(data_points)
        x_step = plot_w / max(n_points - 1, 1)

        coords = []
        for idx, pt in enumerate(data_points):
            x = padding_left + (idx * x_step)
            if pt is not None:
                # Normal latency point
                clamped_pt = min(pt, max_y)
                y = padding_top + plot_h - ((clamped_pt / max_y) * plot_h)
            else:
                # Timed out point plotted at the very top with red marker
                y = padding_top
            coords.append((x, y, pt is not None))

        # Draw connecting line segments
        for i in range(len(coords) - 1):
            x1, y1, valid1 = coords[i]
            x2, y2, valid2 = coords[i + 1]
            line_color = "#00bcd4" if (valid1 and valid2) else "#d32f2f"
            self.canvas.create_line(x1, y1, x2, y2, fill=line_color, width=2)

        # Draw point dots
        for x, y, is_valid in coords:
            dot_color = "#29b6f6" if is_valid else "#f44336"
            r = 3
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=dot_color, outline="")
