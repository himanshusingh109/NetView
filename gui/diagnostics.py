"""
Diagnostics Tab: Direct Ping, DNS Resolver, Route Tracer (Traceroute),
and TCP Client/Server Socket Echo Benchmark.
All operations run on background threads and dispatch results via queue.Queue.
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from network.ping import ping_host
from network.dns import forward_lookup, reverse_lookup
from network.traceroute import run_traceroute
from network.client_server import EchoServer, EchoClient


class DiagnosticsTab(ttk.Frame):
    """Diagnostics view providing network troubleshooting and client-server socket testing."""

    def __init__(self, parent, app=None):
        super().__init__(parent, padding=15)
        self.app = app

        # Traceroute cancellation flag
        self._stop_trace_flag = False

        # Local Echo Server instance
        self.echo_server: Optional[EchoServer] = None

        self._build_ui()

    def _build_ui(self):
        tool_tabs = ttk.Notebook(self)
        tool_tabs.pack(fill=tk.BOTH, expand=True)

        # 1. Quick Ping Test
        ping_frame = ttk.Frame(tool_tabs, padding=15)
        tool_tabs.add(ping_frame, text=" Direct Ping ")
        self._build_ping_subtab(ping_frame)

        # 2. DNS Resolver
        dns_frame = ttk.Frame(tool_tabs, padding=15)
        tool_tabs.add(dns_frame, text=" DNS Resolver ")
        self._build_dns_subtab(dns_frame)

        # 3. Route Tracer (Traceroute)
        trace_frame = ttk.Frame(tool_tabs, padding=15)
        tool_tabs.add(trace_frame, text=" Route Tracer ")
        self._build_trace_subtab(trace_frame)

        # 4. TCP Client/Server Echo Test
        echo_frame = ttk.Frame(tool_tabs, padding=15)
        tool_tabs.add(echo_frame, text=" TCP Echo Test (Client/Server) ")
        self._build_echo_subtab(echo_frame)

    # ---------------- 1. DIRECT PING ----------------

    def _build_ping_subtab(self, parent):
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(ctrl_frame, text="Target IP / Domain:").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_ping_target = ttk.Entry(ctrl_frame, width=26)
        self.entry_ping_target.insert(0, "8.8.8.8")
        self.entry_ping_target.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(ctrl_frame, text="Count:").pack(side=tk.LEFT, padx=(0, 5))
        self.spin_ping_count = ttk.Spinbox(ctrl_frame, from_=1, to=10, width=5)
        self.spin_ping_count.set("4")
        self.spin_ping_count.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_run_ping = ttk.Button(
            ctrl_frame, text="Execute Ping", command=self.handle_run_ping
        )
        self.btn_run_ping.pack(side=tk.LEFT)

        out_frame = ttk.LabelFrame(parent, text="Ping Diagnostic Output", padding=10)
        out_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_ping = tk.Text(out_frame, font=("Consolas", 10), bg="#f8f9fa", relief=tk.FLAT)
        ping_scroll = ttk.Scrollbar(out_frame, orient=tk.VERTICAL, command=self.txt_ping.yview)
        self.txt_ping.configure(yscrollcommand=ping_scroll.set)

        self.txt_ping.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ping_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.txt_ping.insert(tk.END, "Ready. Enter a target and click 'Execute Ping'.\n")
        self.txt_ping.configure(state=tk.DISABLED)

    def handle_run_ping(self):
        target = self.entry_ping_target.get().strip()
        if not target:
            messagebox.showwarning("Input Error", "Please provide a target to ping.")
            return

        try:
            count = int(self.spin_ping_count.get())
        except ValueError:
            count = 4

        self.btn_run_ping.config(state=tk.DISABLED)
        self._write_output(self.txt_ping, f"Pinging {target} ({count} packets)...\nPlease wait...\n", clear=True)

        def worker():
            res = ping_host(target, count=count, timeout_ms=1500)
            if self.app and hasattr(self.app, "event_queue"):
                self.app.event_queue.put({"type": "PING_DIAGNOSTIC", "payload": res})

        threading.Thread(target=worker, daemon=True).start()

    def on_ping_result(self, payload: Dict[str, Any]):
        """Runs on main thread to display ping output."""
        self.btn_run_ping.config(state=tk.NORMAL)
        min_ms = payload.get("min_ms")
        avg_ms = payload.get("avg_ms")
        max_ms = payload.get("max_ms")

        min_str = f"{min_ms}ms" if min_ms is not None else "--"
        avg_str = f"{avg_ms}ms" if avg_ms is not None else "--"
        max_str = f"{max_ms}ms" if max_ms is not None else "--"

        lat_val = payload.get("latency_ms")
        lat_str = f"{lat_val} ms" if lat_val is not None else "--"

        lines = [
            f"=== PING DIAGNOSTIC RESULT ===",
            f"Target:       {payload.get('target')}",
            f"Status:       {payload.get('status')}",
            f"Latency:      {lat_str}",
            f"Min/Avg/Max:  {min_str} / {avg_str} / {max_str}",
            f"Packet Loss:  {payload.get('packet_loss_pct')}%",
            f"Success:      {'YES' if payload.get('success') else 'NO'}",
        ]
        if payload.get("error"):
            lines.append(f"Error Detail: {payload.get('error')}")

        lines.append("\n--- Raw Output ---")
        lines.append(payload.get("raw_output", "").strip())

        self._write_output(self.txt_ping, "\n".join(lines) + "\n", clear=True)

    # ---------------- 2. DNS RESOLVER ----------------

    def _build_dns_subtab(self, parent):
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(ctrl_frame, text="Domain Name or IP Address:").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_dns = ttk.Entry(ctrl_frame, width=28)
        self.entry_dns.insert(0, "google.com")
        self.entry_dns.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_dns_forward = ttk.Button(
            ctrl_frame, text="Forward Lookup (A/AAAA)", command=self.handle_dns_forward
        )
        self.btn_dns_forward.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_dns_reverse = ttk.Button(
            ctrl_frame, text="Reverse Lookup (PTR)", command=self.handle_dns_reverse
        )
        self.btn_dns_reverse.pack(side=tk.LEFT)

        out_frame = ttk.LabelFrame(parent, text="DNS Resolution Records", padding=10)
        out_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_dns = tk.Text(out_frame, font=("Consolas", 10), bg="#f8f9fa", relief=tk.FLAT)
        dns_scroll = ttk.Scrollbar(out_frame, orient=tk.VERTICAL, command=self.txt_dns.yview)
        self.txt_dns.configure(yscrollcommand=dns_scroll.set)

        self.txt_dns.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dns_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.txt_dns.insert(
            tk.END,
            "Ready for DNS query.\n"
            "- Forward Lookup: Resolves domain -> Canonical Name, IPv4, IPv6\n"
            "- Reverse Lookup: Resolves IP address -> PTR Hostname\n"
        )
        self.txt_dns.configure(state=tk.DISABLED)

    def handle_dns_forward(self):
        query = self.entry_dns.get().strip()
        if not query:
            messagebox.showwarning("Input Error", "Please enter a domain name.")
            return

        self._set_dns_buttons(False)
        self._write_output(self.txt_dns, f"Resolving forward DNS for '{query}'...\n", clear=True)

        def worker():
            res = forward_lookup(query)
            if self.app and hasattr(self.app, "event_queue"):
                self.app.event_queue.put({"type": "DNS_RESULT", "payload": ("forward", res)})

        threading.Thread(target=worker, daemon=True).start()

    def handle_dns_reverse(self):
        query = self.entry_dns.get().strip()
        if not query:
            messagebox.showwarning("Input Error", "Please enter an IP address.")
            return

        self._set_dns_buttons(False)
        self._write_output(self.txt_dns, f"Resolving reverse DNS for '{query}'...\n", clear=True)

        def worker():
            res = reverse_lookup(query)
            if self.app and hasattr(self.app, "event_queue"):
                self.app.event_queue.put({"type": "DNS_RESULT", "payload": ("reverse", res)})

        threading.Thread(target=worker, daemon=True).start()

    def _set_dns_buttons(self, state: bool):
        st = tk.NORMAL if state else tk.DISABLED
        self.btn_dns_forward.config(state=st)
        self.btn_dns_reverse.config(state=st)

    def on_dns_result(self, lookup_type: str, payload: Dict[str, Any]):
        """Runs on main thread to display DNS records."""
        self._set_dns_buttons(True)
        lines = []
        if lookup_type == "forward":
            lines.append("=== FORWARD DNS RESOLUTION (Domain -> IPs) ===")
            lines.append(f"Query:          {payload.get('query')}")
            lines.append(f"Canonical Name: {payload.get('canonical_name') or 'N/A'}")
            lines.append(f"IPv4 Addresses: {', '.join(payload.get('ipv4_addresses', [])) or 'None'}")
            lines.append(f"IPv6 Addresses: {', '.join(payload.get('ipv6_addresses', [])) or 'None'}")
        else:
            lines.append("=== REVERSE DNS RESOLUTION (IP -> Hostname PTR) ===")
            lines.append(f"Query:          {payload.get('query')}")
            lines.append(f"PTR Hostname:   {payload.get('hostname') or 'None'}")
            if payload.get("aliases"):
                lines.append(f"Aliases:        {', '.join(payload.get('aliases'))}")

        lines.append(f"Success:        {'YES' if payload.get('success') else 'NO'}")
        if payload.get("error"):
            lines.append(f"Error:          {payload.get('error')}")

        self._write_output(self.txt_dns, "\n".join(lines) + "\n", clear=True)

    # ---------------- 3. ROUTE TRACER (TRACEROUTE) ----------------

    def _build_trace_subtab(self, parent):
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(ctrl_frame, text="Destination Host:").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_trace = ttk.Entry(ctrl_frame, width=26)
        self.entry_trace.insert(0, "1.1.1.1")
        self.entry_trace.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(ctrl_frame, text="Max Hops:").pack(side=tk.LEFT, padx=(0, 5))
        self.spin_hops = ttk.Spinbox(ctrl_frame, from_=5, to=30, width=5)
        self.spin_hops.set("15")
        self.spin_hops.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_start_trace = ttk.Button(
            ctrl_frame, text="Start Route Trace", command=self.handle_start_trace
        )
        self.btn_start_trace.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_stop_trace = ttk.Button(
            ctrl_frame, text="Stop Trace", command=self.handle_stop_trace, state=tk.DISABLED
        )
        self.btn_stop_trace.pack(side=tk.LEFT)

        table_frame = ttk.LabelFrame(parent, text="Hop Discovery Path", padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("hop", "ip", "rtt", "status")
        self.tree_trace = ttk.Treeview(table_frame, columns=cols, show="headings", height=8)
        self.tree_trace.heading("hop", text="Hop #")
        self.tree_trace.heading("ip", text="Router / Gateway IP")
        self.tree_trace.heading("rtt", text="Round-Trip Time")
        self.tree_trace.heading("status", text="Status")

        self.tree_trace.column("hop", width=60, anchor=tk.CENTER)
        self.tree_trace.column("ip", width=220)
        self.tree_trace.column("rtt", width=120, anchor=tk.CENTER)
        self.tree_trace.column("status", width=110, anchor=tk.CENTER)

        self.tree_trace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree_trace.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_trace.configure(yscrollcommand=scroll.set)

    def handle_start_trace(self):
        target = self.entry_trace.get().strip()
        if not target:
            messagebox.showwarning("Input Error", "Please provide a destination host.")
            return

        try:
            max_hops = int(self.spin_hops.get())
        except ValueError:
            max_hops = 15

        self.tree_trace.delete(*self.tree_trace.get_children())
        self._stop_trace_flag = False
        self.btn_start_trace.config(state=tk.DISABLED)
        self.btn_stop_trace.config(state=tk.NORMAL)

        def hop_cb(hop_data):
            if self.app and hasattr(self.app, "event_queue"):
                self.app.event_queue.put({"type": "TRACE_HOP", "payload": hop_data})

        def stop_check():
            return self._stop_trace_flag

        def worker():
            res = run_traceroute(target, max_hops=max_hops, timeout_ms=1000, hop_callback=hop_cb, stop_check=stop_check)
            if self.app and hasattr(self.app, "event_queue"):
                self.app.event_queue.put({"type": "TRACE_COMPLETE", "payload": res})

        threading.Thread(target=worker, daemon=True).start()

    def handle_stop_trace(self):
        self._stop_trace_flag = True
        self.btn_stop_trace.config(state=tk.DISABLED)

    def on_trace_hop(self, hop: Dict[str, Any]):
        """Runs on main thread to add a newly discovered hop to the table."""
        item_id = self.tree_trace.insert(
            "", tk.END,
            values=(hop.get("hop"), hop.get("ip"), hop.get("rtt_display"), hop.get("status"))
        )
        self.tree_trace.see(item_id)

    def on_trace_complete(self, payload: Dict[str, Any]):
        """Runs on main thread when traceroute completes."""
        self.btn_start_trace.config(state=tk.NORMAL)
        self.btn_stop_trace.config(state=tk.DISABLED)

    # ---------------- 4. TCP CLIENT/SERVER ECHO TEST ----------------

    def _build_echo_subtab(self, parent):
        intro_lbl = ttk.Label(
            parent,
            text="TCP Echo Socket Benchmark (Client/Server Programming Syllabus Requirement)\n"
            "Spawns a local TCP socket server, transmits a test payload from a client socket, "
            "verifies payload integrity, and measures round-trip latency.",
            font=("Segoe UI", 9, "italic"),
            foreground="#555555",
        )
        intro_lbl.pack(anchor=tk.W, pady=(0, 12))

        panes = ttk.Frame(parent)
        panes.pack(fill=tk.BOTH, expand=True)

        # Server Box
        server_box = ttk.LabelFrame(panes, text="Local Echo Server (socket.bind / socket.listen)", padding=12)
        server_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(server_box, text="Bind Address: 127.0.0.1 (Loopback)").pack(anchor=tk.W, pady=3)
        ttk.Label(server_box, text="Listen Port:").pack(anchor=tk.W, pady=(5, 2))
        self.entry_echo_port = ttk.Entry(server_box, width=12)
        self.entry_echo_port.insert(0, "9999")
        self.entry_echo_port.pack(anchor=tk.W)

        btn_row = ttk.Frame(server_box)
        btn_row.pack(fill=tk.X, pady=(10, 8))

        self.btn_start_server = ttk.Button(btn_row, text="Start Echo Server", command=self.handle_start_server)
        self.btn_start_server.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_stop_server = ttk.Button(btn_row, text="Stop Server", command=self.handle_stop_server, state=tk.DISABLED)
        self.btn_stop_server.pack(side=tk.LEFT)

        self.lbl_server_status = ttk.Label(
            server_box,
            text="Server State: STOPPED",
            font=("Segoe UI", 9, "bold"),
            foreground="#c62828"
        )
        self.lbl_server_status.pack(anchor=tk.W)

        # Client Box
        client_box = ttk.LabelFrame(panes, text="Test Client (socket.connect / socket.send)", padding=12)
        client_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(client_box, text="Target Address: 127.0.0.1").pack(anchor=tk.W, pady=3)
        ttk.Label(client_box, text="Payload: 32 bytes test packet").pack(anchor=tk.W, pady=3)

        self.btn_run_client = ttk.Button(
            client_box, text="Run Client-Server Round-Trip Test", command=self.handle_run_client
        )
        self.btn_run_client.pack(anchor=tk.W, pady=(10, 8))

        self.lbl_client_result = ttk.Label(
            client_box,
            text="Connection: Standby\nRound-Trip Time: -- ms\nPayload Integrity: Ready",
            font=("Segoe UI", 9),
        )
        self.lbl_client_result.pack(anchor=tk.W)

    def handle_start_server(self):
        try:
            port = int(self.entry_echo_port.get().strip())
        except ValueError:
            messagebox.showwarning("Input Error", "Please provide a valid integer port number.")
            return

        self.echo_server = EchoServer(host="127.0.0.1", port=port)
        started = self.echo_server.start()
        if started:
            self.lbl_server_status.config(
                text=f"Server State: RUNNING (Port: {self.echo_server.actual_port})",
                foreground="#2e7d32"
            )
            self.btn_start_server.config(state=tk.DISABLED)
            self.btn_stop_server.config(state=tk.NORMAL)
        else:
            self.lbl_server_status.config(
                text=f"Server State: ERROR ({self.echo_server.error_message})",
                foreground="#c62828"
            )
            messagebox.showerror("Server Error", self.echo_server.error_message)

    def handle_stop_server(self):
        if self.echo_server:
            self.echo_server.stop()
            self.lbl_server_status.config(text="Server State: STOPPED", foreground="#c62828")
            self.btn_start_server.config(state=tk.NORMAL)
            self.btn_stop_server.config(state=tk.DISABLED)

    def handle_run_client(self):
        try:
            port = int(self.entry_echo_port.get().strip())
        except ValueError:
            port = 9999

        self.lbl_client_result.config(text="Connection: Connecting...\nRound-Trip Time: Measuring...\nPayload Integrity: Testing...")
        self.btn_run_client.config(state=tk.DISABLED)

        def worker():
            client = EchoClient(host="127.0.0.1", port=port, timeout=2.0)
            res = client.test_echo(b"NETVIEW_COLLEGE_SOCKET_TEST")
            if self.app and hasattr(self.app, "event_queue"):
                self.app.event_queue.put({"type": "ECHO_RESULT", "payload": res})

        threading.Thread(target=worker, daemon=True).start()

    def on_echo_result(self, payload: Dict[str, Any]):
        """Runs on main thread to display client/server round-trip test results."""
        self.btn_run_client.config(state=tk.NORMAL)
        if payload.get("success"):
            rtt = payload.get("rtt_ms")
            txt = (
                f"Connection: SUCCESS (Connected to loopback server)\n"
                f"Round-Trip Time: {rtt} ms\n"
                f"Payload Integrity: VERIFIED (Sent & received {payload.get('bytes_sent')} bytes matching)"
            )
            self.lbl_client_result.config(text=txt, foreground="#2e7d32")
        else:
            err = payload.get("error", "Unknown error")
            txt = (
                f"Connection: FAILED\n"
                f"Detail: {err}\n"
                f"(Make sure to click 'Start Echo Server' first)"
            )
            self.lbl_client_result.config(text=txt, foreground="#c62828")

    def _write_output(self, text_widget: tk.Text, text: str, clear: bool = False):
        text_widget.configure(state=tk.NORMAL)
        if clear:
            text_widget.delete("1.0", tk.END)
        text_widget.insert(tk.END, text)
        text_widget.see(tk.END)
        text_widget.configure(state=tk.DISABLED)
