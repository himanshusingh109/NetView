"""
NetView Phase 2 Verification Test Suite.
Validates:
1. Syntax and module imports
2. SQLite table creation and CRUD
3. ICMP Ping with 8.8.8.8
4. Forward DNS with google.com
5. Reverse DNS with 8.8.8.8
6. Traceroute with google.com
7. Local TCP EchoServer and EchoClient benchmark
"""
import os
import sys
import time

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.database import (
    init_db,
    add_host,
    get_all_hosts,
    add_telemetry,
    get_recent_telemetry,
    add_alert,
    get_recent_alerts,
    delete_host,
    DEFAULT_DB_PATH,
)
from network.ping import ping_host
from network.dns import forward_lookup, reverse_lookup
from network.traceroute import run_traceroute
from network.client_server import EchoServer, EchoClient


def run_all_tests():
    test_results = {}
    print("=" * 60)
    print("NETVIEW PHASE 2 VERIFICATION SUITE")
    print("=" * 60)

    # ---------------- 1. Syntax & Import Check ----------------
    print("\n[TEST 1] Syntax & Import Check...")
    try:
        import database.database
        import network.ping
        import network.dns
        import network.traceroute
        import network.client_server
        test_results["1_imports"] = ("PASSED", "All Phase 2 modules imported successfully.")
        print("  -> PASSED")
    except Exception as e:
        test_results["1_imports"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- 2. SQLite Database & Tables Check ----------------
    print("\n[TEST 2] Testing SQLite table creation and CRUD...")
    try:
        # Use an isolated test database file
        test_db = os.path.join(BASE_DIR, "data", "test_netview.db")
        if os.path.exists(test_db):
            os.remove(test_db)

        init_db(test_db)
        # Test adding a host
        hid = add_host("8.8.8.8", "Google DNS", "dns.google", 5, db_path=test_db)
        hosts = get_all_hosts(db_path=test_db)
        assert len(hosts) == 1, "Host count mismatch"
        assert hosts[0]["ip_address"] == "8.8.8.8", "Host IP mismatch"

        # Test adding telemetry
        tid = add_telemetry(hid, 14.5, "ONLINE", 0.0, db_path=test_db)
        telem = get_recent_telemetry(host_id=hid, db_path=test_db)
        assert len(telem) == 1, "Telemetry count mismatch"
        assert telem[0]["latency_ms"] == 14.5, "Telemetry latency mismatch"

        # Test adding alert
        aid = add_alert(hid, "WARNING", "High latency detected", db_path=test_db)
        alerts = get_recent_alerts(db_path=test_db)
        assert len(alerts) == 1, "Alert count mismatch"

        # Test cascading deletion
        delete_host(hid, db_path=test_db)
        assert len(get_all_hosts(db_path=test_db)) == 0, "Host not deleted"
        assert len(get_recent_telemetry(host_id=hid, db_path=test_db)) == 0, "Cascade telemetry failed"

        # Also initialize the production db data/netview.db
        init_db(DEFAULT_DB_PATH)

        # Cleanup test db
        if os.path.exists(test_db):
            os.remove(test_db)

        test_results["2_sqlite"] = ("PASSED", "Tables created, CRUD operations and foreign key cascade verified.")
        print("  -> PASSED")
    except Exception as e:
        test_results["2_sqlite"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- 3. ICMP Ping with 8.8.8.8 ----------------
    print("\n[TEST 3] Testing ICMP Ping with 8.8.8.8...")
    try:
        ping_res = ping_host("8.8.8.8", count=2, timeout_ms=1500)
        print(f"  Result: success={ping_res['success']}, latency={ping_res['latency_ms']}ms, loss={ping_res['packet_loss_pct']}%, status={ping_res['status']}")
        if ping_res["success"] and ping_res["latency_ms"] is not None:
            test_results["3_ping"] = ("PASSED", f"8.8.8.8 ping succeeded: {ping_res['latency_ms']}ms ({ping_res['status']})")
            print("  -> PASSED")
        else:
            test_results["3_ping"] = ("FAILED", f"Ping failed: {ping_res.get('error')}")
            print(f"  -> FAILED: {ping_res.get('error')}")
    except Exception as e:
        test_results["3_ping"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- 4. Forward DNS with google.com ----------------
    print("\n[TEST 4] Testing Forward DNS with google.com...")
    try:
        dns_res = forward_lookup("google.com")
        print(f"  Result: success={dns_res['success']}, canonical={dns_res['canonical_name']}, IPs={dns_res['ipv4_addresses']}")
        if dns_res["success"] and len(dns_res["ipv4_addresses"]) > 0:
            test_results["4_forward_dns"] = ("PASSED", f"google.com resolved to {dns_res['ipv4_addresses']}")
            print("  -> PASSED")
        else:
            test_results["4_forward_dns"] = ("FAILED", f"DNS lookup failed: {dns_res.get('error')}")
            print(f"  -> FAILED: {dns_res.get('error')}")
    except Exception as e:
        test_results["4_forward_dns"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- 5. Reverse DNS with 8.8.8.8 ----------------
    print("\n[TEST 5] Testing Reverse DNS with 8.8.8.8...")
    try:
        rev_res = reverse_lookup("8.8.8.8")
        print(f"  Result: success={rev_res['success']}, hostname={rev_res['hostname']}")
        if rev_res["success"] and rev_res["hostname"]:
            test_results["5_reverse_dns"] = ("PASSED", f"8.8.8.8 resolved to '{rev_res['hostname']}'")
            print("  -> PASSED")
        else:
            test_results["5_reverse_dns"] = ("FAILED", f"Reverse DNS failed: {rev_res.get('error')}")
            print(f"  -> FAILED: {rev_res.get('error')}")
    except Exception as e:
        test_results["5_reverse_dns"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- 6. Traceroute with google.com ----------------
    print("\n[TEST 6] Testing Traceroute with google.com (max 5 hops for test)...")
    try:
        trace_res = run_traceroute("google.com", max_hops=5, timeout_ms=1000)
        print(f"  Result: success={trace_res['success']}, total_hops={trace_res['total_hops']}")
        for h in trace_res["hops"][:3]:
            print(f"    Hop {h['hop']}: IP={h['ip']}, RTT={h['rtt_display']}")
        if trace_res["success"] and trace_res["total_hops"] > 0:
            test_results["6_traceroute"] = ("PASSED", f"Discovered {trace_res['total_hops']} hops for google.com")
            print("  -> PASSED")
        else:
            test_results["6_traceroute"] = ("FAILED", f"Traceroute returned no hops: {trace_res.get('error')}")
            print(f"  -> FAILED: {trace_res.get('error')}")
    except Exception as e:
        test_results["6_traceroute"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- 7. EchoServer & EchoClient Local Benchmark ----------------
    print("\n[TEST 7] Testing EchoServer and EchoClient on local port 9999...")
    try:
        server = EchoServer(host="127.0.0.1", port=9999)
        started = server.start()
        assert started, f"Server failed to start: {server.error_message}"
        print(f"  EchoServer started on port {server.actual_port}, is_running={server.is_running}")

        time.sleep(0.1)  # small pause for server thread ready
        client = EchoClient(host="127.0.0.1", port=server.actual_port, timeout=2.0)
        echo_res = client.test_echo(b"HELLO_NETVIEW_PHASE_2_TEST")
        print(f"  EchoClient result: success={echo_res['success']}, rtt={echo_res['rtt_ms']}ms, verified={echo_res['verified']}")

        # Stop server
        server.stop()
        print(f"  EchoServer stopped, is_running={server.is_running}")

        if echo_res["success"] and echo_res["verified"] and echo_res["rtt_ms"] is not None:
            test_results["7_client_server_echo"] = ("PASSED", f"Echo verified, RTT = {echo_res['rtt_ms']}ms")
            print("  -> PASSED")
        else:
            test_results["7_client_server_echo"] = ("FAILED", f"Echo test failed: {echo_res.get('error')}")
            print(f"  -> FAILED: {echo_res.get('error')}")
    except Exception as e:
        test_results["7_client_server_echo"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    print("\n" + "=" * 60)
    print("SUMMARY OF TEST RESULTS")
    print("=" * 60)
    for test_key, (status, detail) in test_results.items():
        print(f"[{status}] {test_key}: {detail}")
    print("=" * 60)

    return test_results


if __name__ == "__main__":
    run_all_tests()
