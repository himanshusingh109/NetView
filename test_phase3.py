"""
NetView Phase 3 Verification Test Suite.
Validates:
TEST 1: Import all Phase 3 modules.
TEST 2: Create a test host in SQLite.
TEST 3: Start monitoring that host with a short interval.
TEST 4: Verify telemetry records are actually inserted into SQLite.
TEST 5: Verify monitoring can be paused/stopped cleanly.
TEST 6: Verify alert generation for an OFFLINE host or simulated high latency.
TEST 7: Verify CSV export creates valid readable CSV data.
TEST 8: Verify JSON export creates valid readable JSON data.
TEST 9: Verify no duplicate monitoring worker is created when start is called twice.
TEST 10: Verify all worker threads terminate cleanly after stop.
"""
import csv
import json
import os
import queue
import sys
import time

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def run_phase3_tests():
    test_results = {}
    print("=" * 60)
    print("NETVIEW PHASE 3 VERIFICATION SUITE")
    print("=" * 60)

    test_db = os.path.join(BASE_DIR, "data", "test_phase3.db")
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass

    # ---------------- TEST 1: Imports ----------------
    print("\n[TEST 1] Importing all Phase 3 modules...")
    try:
        from database.database import (
            init_db,
            add_host,
            get_host_by_id,
            get_recent_telemetry,
            get_recent_alerts,
        )
        from services.alert_service import AlertService
        from services.export_service import (
            export_telemetry_to_csv,
            export_alerts_to_csv,
            export_history_to_json,
        )
        from services.monitor_service import MonitorService
        test_results["TEST 1 (Imports)"] = ("PASSED", "All Phase 3 services and helpers imported cleanly.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 1 (Imports)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")
        return test_results

    # ---------------- TEST 2: SQLite Test Host Creation ----------------
    print("\n[TEST 2] Creating a test host in SQLite...")
    try:
        init_db(test_db)
        # Using 127.0.0.1 for fast and reliable loopback test ping
        host_id = add_host(
            ip_address="127.0.0.1",
            label="Loopback Test Node",
            hostname="localhost",
            check_interval=1,
            is_active=1,
            db_path=test_db,
        )
        host = get_host_by_id(host_id, db_path=test_db)
        assert host is not None, "Failed to retrieve inserted host"
        assert host["ip_address"] == "127.0.0.1", "Host IP mismatch"
        assert host["check_interval"] == 1, "Host interval mismatch"
        test_results["TEST 2 (Host Creation)"] = ("PASSED", f"Created host id={host_id} (127.0.0.1) in SQLite.")
        print(f"  -> PASSED (host_id={host_id})")
    except Exception as e:
        test_results["TEST 2 (Host Creation)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 3: Start Monitoring Host ----------------
    print("\n[TEST 3] Starting background monitor service with short interval (1s)...")
    event_q = queue.Queue()
    alert_svc = AlertService(warning_latency_ms=150.0, critical_latency_ms=300.0)
    monitor = MonitorService(event_queue=event_q, alert_service=alert_svc, db_path=test_db)

    try:
        started = monitor.start_host(host)
        assert started is True, "Failed to start monitoring worker thread"
        assert monitor.is_host_running(host_id) is True, "Worker thread is not marked as running"
        test_results["TEST 3 (Start Monitor)"] = ("PASSED", "Worker daemon thread launched successfully.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 3 (Start Monitor)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 4: Telemetry Insert Verification ----------------
    print("\n[TEST 4] Verifying telemetry records inserted into SQLite...")
    try:
        # Wait 2.5 seconds to let worker complete at least 2 ping iterations
        time.sleep(2.5)

        records = get_recent_telemetry(host_id=host_id, db_path=test_db)
        print(f"  Retrieved {len(records)} telemetry records from SQLite.")
        assert len(records) >= 1, "No telemetry records found in database"
        sample = records[0]
        print(f"  Sample Record: latency={sample['latency_ms']}ms, status={sample['status']}, timestamp={sample['timestamp']}")
        assert sample["status"] in ("ONLINE", "HIGH_LATENCY"), "Status unexpected"
        assert sample["host_id"] == host_id, "Host ID reference mismatch"

        # Check that events arrived in queue
        queue_events = []
        while not event_q.empty():
            queue_events.append(event_q.get_nowait())
        print(f"  Queue received {len(queue_events)} events during monitoring.")
        assert len(queue_events) >= 1, "No events found in queue.Queue"

        test_results["TEST 4 (Telemetry SQLite)"] = (
            "PASSED",
            f"Successfully inserted {len(records)} telemetry rows and dispatched queue events.",
        )
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 4 (Telemetry SQLite)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 5: Pause and Resume Functionality ----------------
    print("\n[TEST 5] Verifying pause and resume functionality...")
    try:
        monitor.pause_host(host_id)
        assert monitor.is_paused(host_id) is True, "Host was not marked as paused"
        print("  Host paused successfully.")

        monitor.resume_host(host_id)
        assert monitor.is_paused(host_id) is False, "Host was not resumed"
        print("  Host resumed successfully.")

        test_results["TEST 5 (Pause/Resume)"] = ("PASSED", "Pause and resume states verified cleanly.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 5 (Pause/Resume)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 6: Alert Generation for Offline/High Latency ----------------
    print("\n[TEST 6] Verifying alert generation for OFFLINE and high-latency conditions...")
    try:
        # Simulate offline telemetry
        simulated_offline = {
            "success": False,
            "latency_ms": None,
            "status": "OFFLINE",
            "error": "Request timed out",
        }
        offline_alert = alert_svc.evaluate(
            host_id=host_id,
            host_label="Loopback Test Node",
            ip_address="127.0.0.1",
            telemetry=simulated_offline,
            db_path=test_db,
        )
        assert offline_alert is not None, "Offline alert was not triggered"
        assert offline_alert["severity"] == "CRITICAL", "Offline severity should be CRITICAL"
        print(f"  Offline Alert Triggered: {offline_alert['message']}")

        # Verify duplicate offline alert is suppressed on next cycle
        dup_alert = alert_svc.evaluate(
            host_id=host_id,
            host_label="Loopback Test Node",
            ip_address="127.0.0.1",
            telemetry=simulated_offline,
            db_path=test_db,
        )
        assert dup_alert is None, "Duplicate offline alert should be suppressed"
        print("  Duplicate alert suppression verified.")

        # Simulate High Latency (e.g. 200ms -> WARNING)
        simulated_high_latency = {
            "success": True,
            "latency_ms": 220.0,
            "status": "HIGH_LATENCY",
            "packet_loss_pct": 0.0,
        }
        hl_alert = alert_svc.evaluate(
            host_id=host_id,
            host_label="Loopback Test Node",
            ip_address="127.0.0.1",
            telemetry=simulated_high_latency,
            db_path=test_db,
        )
        assert hl_alert is not None, "High latency alert was not triggered"
        assert hl_alert["severity"] == "WARNING", "High latency severity should be WARNING"
        print(f"  High Latency Alert Triggered: {hl_alert['message']}")

        # Verify alerts stored in SQLite
        db_alerts = get_recent_alerts(db_path=test_db)
        assert len(db_alerts) >= 2, "Alerts were not persisted to SQLite"

        test_results["TEST 6 (Alert Generation)"] = (
            "PASSED",
            f"Generated CRITICAL and WARNING alerts; verified duplicate suppression and SQLite persistence.",
        )
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 6 (Alert Generation)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 7: CSV Export ----------------
    print("\n[TEST 7] Verifying CSV export of telemetry records...")
    csv_path = os.path.join(BASE_DIR, "data", "test_telemetry.csv")
    try:
        csv_res = export_telemetry_to_csv(filepath=csv_path, db_path=test_db)
        assert csv_res["success"] is True, f"CSV export failed: {csv_res.get('error')}"
        assert os.path.exists(csv_path), "CSV file was not created"

        # Read and validate CSV contents
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert "latency_ms" in header, "Missing expected CSV header"
            rows = list(reader)
            assert len(rows) > 0, "CSV file has no data rows"
            print(f"  CSV exported {len(rows)} data rows. Header: {header}")

        test_results["TEST 7 (CSV Export)"] = ("PASSED", f"Exported {len(rows)} rows to valid CSV.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 7 (CSV Export)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")
    finally:
        if os.path.exists(csv_path):
            try:
                os.remove(csv_path)
            except Exception:
                pass

    # ---------------- TEST 8: JSON Export ----------------
    print("\n[TEST 8] Verifying JSON export of system history...")
    json_path = os.path.join(BASE_DIR, "data", "test_history.json")
    try:
        json_res = export_history_to_json(filepath=json_path, db_path=test_db)
        assert json_res["success"] is True, f"JSON export failed: {json_res.get('error')}"
        assert os.path.exists(json_path), "JSON file was not created"

        # Read and validate JSON contents
        with open(json_path, mode="r", encoding="utf-8") as f:
            parsed = json.load(f)
            assert "metadata" in parsed, "JSON missing metadata"
            assert "hosts" in parsed, "JSON missing hosts array"
            assert "telemetry" in parsed, "JSON missing telemetry array"
            assert "alerts" in parsed, "JSON missing alerts array"
            print(f"  JSON verified: {len(parsed['telemetry'])} telemetry records, {len(parsed['alerts'])} alerts.")

        test_results["TEST 8 (JSON Export)"] = ("PASSED", "JSON structure and data verified.")
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 8 (JSON Export)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")
    finally:
        if os.path.exists(json_path):
            try:
                os.remove(json_path)
            except Exception:
                pass

    # ---------------- TEST 9: Duplicate Worker Prevention ----------------
    print("\n[TEST 9] Verifying duplicate monitoring worker prevention...")
    try:
        # Worker is already running for host_id
        second_start = monitor.start_host(host)
        assert second_start is False, "Duplicate worker thread was incorrectly started"
        assert monitor.active_worker_count == 1, "Worker count should remain exactly 1"
        test_results["TEST 9 (No Duplicate Workers)"] = (
            "PASSED",
            "Duplicate start request rejected, exactly 1 worker running.",
        )
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 9 (No Duplicate Workers)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- TEST 10: Clean Thread Termination ----------------
    print("\n[TEST 10] Verifying clean worker thread termination on stop...")
    try:
        worker_thread = monitor._workers.get(host_id)
        assert worker_thread is not None and worker_thread.is_alive(), "Worker was not running before stop"

        monitor.stop_all(timeout=3.0)
        time.sleep(0.5)

        assert monitor.active_worker_count == 0, f"Workers still active: {monitor.active_worker_count}"
        assert not worker_thread.is_alive(), "Worker thread is still alive after stop_all"

        test_results["TEST 10 (Clean Termination)"] = (
            "PASSED",
            "All worker threads joined and terminated cleanly.",
        )
        print("  -> PASSED")
    except Exception as e:
        test_results["TEST 10 (Clean Termination)"] = ("FAILED", str(e))
        print(f"  -> FAILED: {e}")

    # ---------------- Cleanup Test Database ----------------
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass

    # ---------------- Print Summary ----------------
    print("\n" + "=" * 60)
    print("PHASE 3 TEST SUMMARY")
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
    run_phase3_tests()
