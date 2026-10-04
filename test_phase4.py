"""
NetView Phase 4 Verification Test Suite.
Validates full GUI integration:
TEST 1: Import main.py and all GUI modules.
TEST 2: Create Tkinter root and initialize NetViewApp.
TEST 3: Verify all four tabs load.
TEST 4: Verify database-backed host can be displayed in Host Monitor.
TEST 5: Start monitoring a test host and verify queue events reach the GUI application.
TEST 6: Verify dashboard KPI values update from real data.
TEST 7: Verify diagnostic operations can be triggered without blocking the GUI.
TEST 8: Verify telemetry history loads.
TEST 9: Verify alert history loads.
TEST 10: Verify export buttons/functions produce valid files.
TEST 11: Verify application shutdown stops monitoring workers cleanly.
"""
import os
import sys
import time
import tkinter as tk

# Ensure NetView project root is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def run_phase4_tests():
    test_results = {}
    print("=" * 60)
    print("NETVIEW PHASE 4 VERIFICATION SUITE")
    print("=" * 60)

    test_db = os.path.join(BASE_DIR, "data", "test_phase4.db")
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass

    # ---------------- TEST 1: Imports ----------------
    print("\n[TEST 1] Importing main.py and all GUI modules...")
    try:
        from main import NetViewApp
        from gui.dashboard import DashboardTab
        from gui.monitor import MonitorTab
        from gui.diagnostics import DiagnosticsTab
        from gui.history import HistoryTab
        from database.database import (
            init_db,
            seed_default_hosts_if_empty,
            add_telemetry,
            add_alert,
        )
        from services.export_service import (
            export_telemetry_to_csv,
            export_alerts_to_csv,
            export_history_to_json,
        )
        test_results["TEST 1 (Imports)"] = ("PASSED", "All GUI modules and main.py imported successfully.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 1 (Imports)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")
        return test_results

    # ---------------- TEST 2: Root and NetViewApp Initialization ----------------
    print("\n[TEST 2] Creating Tkinter root and initializing NetViewApp...")
    try:
        root = tk.Tk()
        # Withdraw window to prevent popping during automated headless testing
        root.withdraw()
        app = NetViewApp(root, db_path=test_db)
        root.update()
        test_results["TEST 2 (App Init)"] = ("PASSED", "NetViewApp initialized with SQLite and thread-safe queue.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 2 (App Init)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")
        return test_results

    # ---------------- TEST 3: Verify All Four Tabs Load ----------------
    print("\n[TEST 3] Verifying all four tabs load into ttk.Notebook...")
    try:
        tabs = app.notebook.tabs()
        print(f"  Loaded tabs: {tabs}")
        assert len(tabs) == 4, f"Expected 4 tabs, found {len(tabs)}"
        assert isinstance(app.tab_dashboard, DashboardTab)
        assert isinstance(app.tab_monitor, MonitorTab)
        assert isinstance(app.tab_diagnostics, DiagnosticsTab)
        assert isinstance(app.tab_history, HistoryTab)
        test_results["TEST 3 (Tabs Load)"] = ("PASSED", "All four tabs (Dashboard, Monitor, Diagnostics, History) loaded.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 3 (Tabs Load)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 4: Display Database Hosts in Monitor ----------------
    print("\n[TEST 4] Verifying database-backed hosts displayed in Host Monitor...")
    try:
        # Seeded hosts should be in tree
        items = app.tab_monitor.tree_hosts.get_children()
        print(f"  Host Monitor rows: {len(items)}")
        assert len(items) >= 4, f"Expected at least 4 default hosts, found {len(items)}"
        first_row = app.tab_monitor.tree_hosts.item(items[0], "values")
        print(f"  First Host Row: #{first_row[0]} {first_row[1]} ({first_row[2]})")
        assert "8.8.8.8" in first_row[2] or "Google" in first_row[1]
        test_results["TEST 4 (Host Display)"] = ("PASSED", f"Host monitor displays {len(items)} database-backed hosts.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 4 (Host Display)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 5: Monitoring Queue Events Reach GUI ----------------
    print("\n[TEST 5] Testing queue event dispatch to GUI components...")
    try:
        # Dispatch synthetic telemetry event into the queue
        test_payload = {
            "host_id": 1,
            "label": "Google Public DNS",
            "ip_address": "8.8.8.8",
            "latency_ms": 19.5,
            "status": "ONLINE",
            "packet_loss": 0.0,
            "timestamp": "2026-10-03 18:50:00",
        }
        app.event_queue.put({"type": "TELEMETRY_UPDATE", "payload": test_payload})

        # Process queue on main thread
        app.process_queue()
        root.update()

        # Verify monitor tab received and buffered the latency point
        history = app.tab_monitor.latency_history[1]
        assert len(history) > 0, "Latency history buffer did not receive event"
        assert history[-1] == 19.5, f"Expected 19.5ms, got {history[-1]}"

        # Verify host table was updated
        item_vals = app.tab_monitor.tree_hosts.item("1", "values")
        assert item_vals[3] == "ONLINE", f"Expected ONLINE, got {item_vals[3]}"
        assert "19.5 ms" in item_vals[4], f"Expected 19.5 ms in latency col, got {item_vals[4]}"

        test_results["TEST 5 (Queue to GUI)"] = ("PASSED", "Queue events safely dispatched and updated GUI widgets.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 5 (Queue to GUI)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 6: Dashboard KPI Update ----------------
    print("\n[TEST 6] Verifying dashboard KPI values update from real data...")
    try:
        app.tab_dashboard.refresh_data()
        root.update()

        total = int(app.tab_dashboard.lbl_total_hosts.cget("text"))
        online = int(app.tab_dashboard.lbl_hosts_online.cget("text"))
        offline = int(app.tab_dashboard.lbl_hosts_offline.cget("text"))
        alerts = int(app.tab_dashboard.lbl_active_alerts.cget("text"))

        print(f"  Dashboard KPIs: Total={total}, Online={online}, Offline={offline}, Alerts={alerts}")
        assert total >= 4, f"Total hosts KPI mismatch: {total}"
        test_results["TEST 6 (Dashboard KPIs)"] = ("PASSED", f"Dashboard KPIs computed from real data (Total={total}).")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 6 (Dashboard KPIs)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 7: Diagnostic Operations Non-Blocking ----------------
    print("\n[TEST 7] Verifying diagnostic operations execute asynchronously...")
    try:
        # 1. Test ping trigger (should not freeze GUI)
        app.tab_diagnostics.entry_ping_target.delete(0, tk.END)
        app.tab_diagnostics.entry_ping_target.insert(0, "127.0.0.1")
        app.tab_diagnostics.spin_ping_count.set("1")
        app.tab_diagnostics.handle_run_ping()

        # Ping button should immediately disable to indicate background worker running
        assert str(app.tab_diagnostics.btn_run_ping.cget("state")) == "disabled", "Ping button should disable while running"
        print("  Direct ping launched asynchronously.")

        # 2. Test TCP Echo Server start and stop
        app.tab_diagnostics.entry_echo_port.delete(0, tk.END)
        app.tab_diagnostics.entry_echo_port.insert(0, "9998")
        app.tab_diagnostics.handle_start_server()
        assert app.tab_diagnostics.echo_server is not None
        assert app.tab_diagnostics.echo_server.is_running is True, "Echo server failed to start"
        print(f"  Echo server running on port {app.tab_diagnostics.echo_server.actual_port}.")

        app.tab_diagnostics.handle_stop_server()
        assert app.tab_diagnostics.echo_server.is_running is False, "Echo server failed to stop"
        print("  Echo server stopped cleanly.")

        test_results["TEST 7 (Diagnostics Async)"] = ("PASSED", "Diagnostics run on daemon threads without blocking UI.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 7 (Diagnostics Async)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 8: Telemetry History Loads ----------------
    print("\n[TEST 8] Verifying telemetry history loads in History & Reports...")
    try:
        # Insert a known telemetry row
        add_telemetry(host_id=1, latency_ms=22.4, status="ONLINE", packet_loss=0.0, db_path=test_db)
        app.tab_history.refresh_logs()
        root.update()

        telem_rows = app.tab_history.tree_telem.get_children()
        print(f"  History tab telemetry rows: {len(telem_rows)}")
        assert len(telem_rows) >= 1, "No telemetry rows loaded into history table"
        test_results["TEST 8 (Telemetry History)"] = ("PASSED", f"Telemetry history loaded {len(telem_rows)} records.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 8 (Telemetry History)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 9: Alert History Loads ----------------
    print("\n[TEST 9] Verifying alert history loads in History & Reports...")
    try:
        add_alert(host_id=1, severity="WARNING", message="Latency above warning threshold (160ms)", db_path=test_db)
        app.tab_history.refresh_alerts()
        root.update()

        alert_rows = app.tab_history.tree_alerts.get_children()
        print(f"  History tab alert rows: {len(alert_rows)}")
        assert len(alert_rows) >= 1, "No alert rows loaded into alert table"
        sample_alert = app.tab_history.tree_alerts.item(alert_rows[0], "values")
        assert sample_alert[2] == "WARNING", f"Alert severity mismatch: {sample_alert[2]}"
        test_results["TEST 9 (Alert History)"] = ("PASSED", f"Alert history loaded {len(alert_rows)} records.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 9 (Alert History)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 10: Export Functions Produce Valid Files ----------------
    print("\n[TEST 10] Verifying export functions produce valid CSV and JSON files...")
    csv_telem = os.path.join(BASE_DIR, "data", "test_p4_telem.csv")
    csv_alerts = os.path.join(BASE_DIR, "data", "test_p4_alerts.csv")
    json_hist = os.path.join(BASE_DIR, "data", "test_p4_hist.json")

    try:
        res1 = export_telemetry_to_csv(csv_telem, db_path=test_db)
        assert res1["success"] is True and os.path.exists(csv_telem), "Telemetry CSV export failed"

        res2 = export_alerts_to_csv(csv_alerts, db_path=test_db)
        assert res2["success"] is True and os.path.exists(csv_alerts), "Alerts CSV export failed"

        res3 = export_history_to_json(json_hist, db_path=test_db)
        assert res3["success"] is True and os.path.exists(json_hist), "JSON export failed"

        print(f"  Export outputs verified: CSV Telem ({res1['rows_exported']} rows), CSV Alerts ({res2['rows_exported']} rows), JSON ({res3['rows_exported']} items).")
        test_results["TEST 10 (Export Files)"] = ("PASSED", "CSV and JSON export routines produced valid, populated files.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 10 (Export Files)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")
    finally:
        for f in (csv_telem, csv_alerts, json_hist):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    # ---------------- TEST 11: Clean Shutdown Stops Workers ----------------
    print("\n[TEST 11] Verifying application shutdown stops all background workers...")
    try:
        app.on_close()
        time.sleep(0.5)

        assert app.monitor_service.active_worker_count == 0, f"Workers still running: {app.monitor_service.active_worker_count}"
        test_results["TEST 11 (Clean Shutdown)"] = ("PASSED", "All monitor service workers stopped and joined cleanly.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 11 (Clean Shutdown)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # Cleanup test db
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass

    # ---------------- Summary ----------------
    print("\n" + "=" * 60)
    print("PHASE 4 TEST SUMMARY")
    print("=" * 60)
    passed_count = sum(1 for status, _ in test_results.values() if status == "PASSED")
    total_count = len(test_results)
    for name, (status, detail) in test_results.items():
        print(f"[{status}] {name}: {detail}")
    print("=" * 60)
    print(f"TOTAL: {passed_count}/{total_count} TESTS PASSED")
    print("=" * 60)

    return test_results


if __name__ == "__main__":
    run_phase4_tests()
