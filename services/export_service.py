"""
Export Service for NetView.
Exports telemetry logs and alert history to CSV and JSON formats using Python
standard library csv and json modules with robust file error handling.
"""
import csv
import json
import os
from typing import Dict, Any, Optional
from database.database import (
    get_all_hosts,
    get_recent_telemetry,
    get_recent_alerts,
)


def export_telemetry_to_csv(
    filepath: str,
    host_id: Optional[int] = None,
    limit: int = 1000,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Exports historical telemetry records to a CSV file.

    Returns:
        dict: {"success": bool, "rows_exported": int, "filepath": str, "error": Optional[str]}
    """
    result: Dict[str, Any] = {
        "success": False,
        "rows_exported": 0,
        "filepath": filepath,
        "error": None,
    }

    try:
        records = get_recent_telemetry(host_id=host_id, limit=limit, db_path=db_path)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        fieldnames = ["id", "host_id", "host_label", "ip_address", "timestamp", "latency_ms", "packet_loss", "status"]

        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in records:
                writer.writerow(row)

        result["success"] = True
        result["rows_exported"] = len(records)
    except Exception as e:
        result["error"] = f"Failed to export telemetry CSV: {str(e)}"

    return result


def export_alerts_to_csv(
    filepath: str,
    limit: int = 1000,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Exports alert events to a CSV file.

    Returns:
        dict: {"success": bool, "rows_exported": int, "filepath": str, "error": Optional[str]}
    """
    result: Dict[str, Any] = {
        "success": False,
        "rows_exported": 0,
        "filepath": filepath,
        "error": None,
    }

    try:
        alerts = get_recent_alerts(limit=limit, db_path=db_path)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        fieldnames = ["id", "host_id", "host_label", "ip_address", "timestamp", "severity", "message"]

        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in alerts:
                writer.writerow(row)

        result["success"] = True
        result["rows_exported"] = len(alerts)
    except Exception as e:
        result["error"] = f"Failed to export alerts CSV: {str(e)}"

    return result


def export_history_to_json(
    filepath: str,
    host_id: Optional[int] = None,
    limit: int = 500,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Exports combined system history (hosts, telemetry, and alerts) to a JSON file.

    Returns:
        dict: {"success": bool, "rows_exported": int, "filepath": str, "error": Optional[str]}
    """
    result: Dict[str, Any] = {
        "success": False,
        "rows_exported": 0,
        "filepath": filepath,
        "error": None,
    }

    try:
        hosts = get_all_hosts(db_path=db_path)
        telemetry = get_recent_telemetry(host_id=host_id, limit=limit, db_path=db_path)
        alerts = get_recent_alerts(limit=limit, db_path=db_path)

        export_data = {
            "metadata": {
                "generated_by": "NetView Network Monitoring System",
                "total_hosts": len(hosts),
                "total_telemetry_records": len(telemetry),
                "total_alert_records": len(alerts),
            },
            "hosts": hosts,
            "telemetry": telemetry,
            "alerts": alerts,
        }

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(filepath, mode="w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)

        total_records = len(telemetry) + len(alerts)
        result["success"] = True
        result["rows_exported"] = total_records
    except Exception as e:
        result["error"] = f"Failed to export history JSON: {str(e)}"

    return result
