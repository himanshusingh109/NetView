"""
Dashboard Tab: Live system overview, network profile, KPI summary cards,
quick host status table, and recent activity log.
Connected to real SQLite database, network probers, and queue dispatching.
"""
import re
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any

from database.database import (
    get_all_hosts,
    get_recent_telemetry,
    get_recent_alerts,
)
from network.ping import ping_host


class DashboardTab(ttk.Frame):
    """Dashboard view presenting live system telemetry, network profile, and event activity."""

    def __init__(self, parent, app=None):
        super().__init__(parent, padding=15)
        self.app = app
        self._build_ui()
        self.refresh_data()
        self.detect_network_profile_async()

    def _build_ui(self):
        # 1. Header Banner
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 12))

        title_label = ttk.Label(
            header_frame,
            text="System Overview & Network Health",
            font=("Segoe UI", 13, "bold"),
        )
        title_label.pack(side=tk.LEFT)

        self.status_badge = ttk.Label(
            header_frame,
            text="[ MONITORING ACTIVE ]",
            font=("Segoe UI", 9, "bold"),
            foreground="#2e7d32",
        )
        self.status_badge.pack(side=tk.RIGHT)

        # 2. KPI Metric Cards Row
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill=tk.X, pady=(0, 12))

        def create_card(parent, title, default_val, accent_color="#2b2b2b"):
            card = ttk.LabelFrame(parent, text=title, padding=10)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            val_lbl = tk.Label(
                card,
                text=default_val,
                font=("Segoe UI", 17, "bold"),
                fg=accent_color,
            )
            val_lbl.pack(anchor=tk.CENTER)
            return val_lbl

        self.lbl_total_hosts = create_card(cards_frame, "Total Monitored", "0", "#2b2b2b")
        self.lbl_hosts_online = create_card(cards_frame, "Hosts Online", "0", "#2e7d32")
        self.lbl_hosts_offline = create_card(cards_frame, "Hosts Offline", "0", "#c62828")
        self.lbl_active_alerts = create_card(cards_frame, "Recent Alerts", "0", "#ef6c00")

        # 3. Middle Section: Local Profile (Left) and Quick Status Table (Right)
        mid_frame = ttk.Frame(self)
        mid_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        # Left: Local Network Profile
        net_profile_frame = ttk.LabelFrame(mid_frame, text="Local Network Profile", padding=12)
        net_profile_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))

        profile_grid = ttk.Frame(net_profile_frame)
        profile_grid.pack(fill=tk.BOTH, expand=True)

        rows = [
            ("Local Hostname:", "Detecting..."),
            ("Local IP Address:", "Detecting..."),
            ("Default Gateway:", "Detecting..."),
            ("Internet Status:", "Testing..."),
        ]

        self.profile_labels = {}
        for idx, (label_text, default_val) in enumerate(rows):
            ttk.Label(
                profile_grid, text=label_text, font=("Segoe UI", 9, "bold")
            ).grid(row=idx, column=0, sticky=tk.W, pady=4, padx=(0, 10))
            val = ttk.Label(profile_grid, text=default_val, font=("Segoe UI", 9))
            val.grid(row=idx, column=1, sticky=tk.W, pady=4)
            self.profile_labels[label_text] = val

        # Refresh Profile Button
        btn_refresh_profile = ttk.Button(
            net_profile_frame,
            text="Re-Detect Profile",
            command=self.detect_network_profile_async,
        )
        btn_refresh_profile.pack(fill=tk.X, pady=(8, 0))

        # Right: Quick Status Table
        quick_status_frame = ttk.LabelFrame(mid_frame, text="Active Target Nodes", padding=8)
        quick_status_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("id", "label", "target", "latency", "status", "checked")
        self.quick_tree = ttk.Treeview(
            quick_status_frame, columns=columns, show="headings", height=6
        )
        self.quick_tree.heading("id", text="#")
        self.quick_tree.heading("label", text="Host Label")
        self.quick_tree.heading("target", text="IP / Domain")
        self.quick_tree.heading("latency", text="Latest Latency")
        self.quick_tree.heading("status", text="Status")
        self.quick_tree.heading("checked", text="Last Checked")

        self.quick_tree.column("id", width=30, anchor=tk.CENTER)
        self.quick_tree.column("label", width=120)
        self.quick_tree.column("target", width=120)
        self.quick_tree.column("latency", width=95, anchor=tk.CENTER)
        self.quick_tree.column("status", width=95, anchor=tk.CENTER)
        self.quick_tree.column("checked", width=85, anchor=tk.CENTER)

        quick_scroll = ttk.Scrollbar(
            quick_status_frame, orient=tk.VERTICAL, command=self.quick_tree.yview
        )
        self.quick_tree.configure(yscrollcommand=quick_scroll.set)

        self.quick_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        quick_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 4. Bottom Section: Real-time Event Feed
        log_frame = ttk.LabelFrame(self, text="Recent Activity & Events", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            log_frame,
            height=5,
            font=("Consolas", 9),
            bg="#f8f9fa",
            fg="#212529",
            relief=tk.FLAT,
        )
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text.insert(
            tk.END,
            f"[{time.strftime('%H:%M:%S')}] [SYSTEM] NetView Dashboard ready.\n"
        )
        self.log_text.configure(state=tk.DISABLED)

    # ---------------- DATA REFRESH & EVENT HANDLERS ----------------

    def refresh_data(self):
        """Loads actual data from SQLite and populates the dashboard overview."""
        db_path = self.app.db_path if self.app else None
        hosts = get_all_hosts(db_path=db_path)
        recent_telem = get_recent_telemetry(limit=100, db_path=db_path)
        recent_alerts = get_recent_alerts(limit=50, db_path=db_path)

        # Map latest telemetry per host_id
        latest_by_host = {}
        for r in recent_telem:
            hid = r["host_id"]
            if hid not in latest_by_host:
                latest_by_host[hid] = r

        # Clear and repopulate Quick Tree
        self.quick_tree.delete(*self.quick_tree.get_children())

        online_count = 0
        offline_count = 0

        for h in hosts:
            hid = h["id"]
            label = h["label"]
            ip = h["ip_address"]
            telem = latest_by_host.get(hid)

            if telem:
                lat = f"{telem['latency_ms']} ms" if telem["latency_ms"] is not None else "--"
                st = telem["status"]
                ts = telem["timestamp"].split(" ")[-1] if " " in telem["timestamp"] else telem["timestamp"]
                if st in ("ONLINE", "HIGH_LATENCY"):
                    online_count += 1
                else:
                    offline_count += 1
            else:
                lat = "--"
                st = "STANDBY"
                ts = "--"

            self.quick_tree.insert(
                "", tk.END, iid=str(hid), values=(hid, label, ip, lat, st, ts)
            )

        # Update KPI Cards
        self.lbl_total_hosts.config(text=str(len(hosts)))
        self.lbl_hosts_online.config(text=str(online_count))
        self.lbl_hosts_offline.config(text=str(offline_count))
        self.lbl_active_alerts.config(text=str(len(recent_alerts)))

    def on_telemetry(self, payload: Dict[str, Any]):
        """Called by main queue processor when a new telemetry check arrives."""
        hid = str(payload["host_id"])
        lat = f"{payload['latency_ms']} ms" if payload.get("latency_ms") is not None else "--"
        st = payload.get("status", "OFFLINE")
        ts = payload.get("timestamp", "").split(" ")[-1]

        # Update existing tree row if present
        if self.quick_tree.exists(hid):
            current_vals = list(self.quick_tree.item(hid, "values"))
            current_vals[3] = lat
            current_vals[4] = st
            current_vals[5] = ts
            self.quick_tree.item(hid, values=current_vals)

        # Re-tally online/offline counts from visible tree items
        online = 0
        offline = 0
        total = 0
        for item in self.quick_tree.get_children():
            total += 1
            item_st = self.quick_tree.item(item, "values")[4]
            if item_st in ("ONLINE", "HIGH_LATENCY"):
                online += 1
            elif item_st == "OFFLINE":
                offline += 1

        self.lbl_total_hosts.config(text=str(total))
        self.lbl_hosts_online.config(text=str(online))
        self.lbl_hosts_offline.config(text=str(offline))

        # Log event in activity box
        self.log_event(
            f"[POLL] {payload.get('label')} ({payload.get('ip_address')}): {st} (RTT: {lat})"
        )

    def on_alert(self, payload: Dict[str, Any]):
        """Called by main queue processor when an alert event is triggered."""
        sev = payload.get("severity", "WARNING")
        msg = payload.get("message", "Alert")
        self.log_event(f"[{sev}] {msg}")
        # Increment alerts counter
        try:
            cur = int(self.lbl_active_alerts.cget("text"))
            self.lbl_active_alerts.config(text=str(cur + 1))
        except Exception:
            pass

    def log_event(self, text: str):
        """Appends a timestamped line to the activity feed."""
        t_str = time.strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{t_str}] {text}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ---------------- NETWORK PROFILE AUTO-DETECTION ----------------

    def detect_network_profile_async(self):
        """Spawns a background thread to inspect the local network without blocking UI."""
        thread = threading.Thread(target=self._detect_profile_worker, daemon=True)
        thread.start()

    def _detect_profile_worker(self):
        """Worker inspecting hostname, primary outbound IP, gateway, and internet reachability."""
        profile = {
            "hostname": "Unknown",
            "ip": "Unknown",
            "gateway": "Unknown",
            "internet": "Offline",
        }

        # 1. Hostname
        try:
            profile["hostname"] = socket.gethostname()
        except Exception:
            profile["hostname"] = "localhost"

        # 2. Local Outbound IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            profile["ip"] = s.getsockname()[0]
            s.close()
        except Exception:
            try:
                profile["ip"] = socket.gethostbyname(profile["hostname"])
            except Exception:
                profile["ip"] = "127.0.0.1"

        # 3. Default Gateway
        try:
            if sys.platform.startswith("win"):
                proc = subprocess.run(
                    ["ipconfig"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3,
                )
                gw_match = re.search(r"Default Gateway[ .]*:\s*([0-9]{1,3}(?:\.[0-9]{1,3}){3})", proc.stdout)
                if gw_match:
                    profile["gateway"] = gw_match.group(1)
        except Exception:
            profile["gateway"] = "Unavailable"

        # 4. Internet reachability probe
        try:
            ping_res = ping_host("8.8.8.8", count=1, timeout_ms=1200)
            if ping_res["success"]:
                profile["internet"] = f"Online ({ping_res['latency_ms']}ms)"
            else:
                profile["internet"] = "No Internet (ICMP timeout)"
        except Exception:
            profile["internet"] = "Unreachable"

        # Send to main queue
        if self.app and hasattr(self.app, "event_queue"):
            self.app.event_queue.put({"type": "NETWORK_PROFILE", "payload": profile})

    def update_network_profile_ui(self, profile: Dict[str, str]):
        """Runs on main thread to update profile label widgets."""
        if "Local Hostname:" in self.profile_labels:
            self.profile_labels["Local Hostname:"].config(text=profile.get("hostname", "Unknown"))
        if "Local IP Address:" in self.profile_labels:
            self.profile_labels["Local IP Address:"].config(text=profile.get("ip", "Unknown"))
        if "Default Gateway:" in self.profile_labels:
            self.profile_labels["Default Gateway:"].config(text=profile.get("gateway", "Unknown"))
        if "Internet Status:" in self.profile_labels:
            self.profile_labels["Internet Status:"].config(text=profile.get("internet", "Unknown"))
