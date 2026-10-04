"""
Network Ping Module for NetView.
Performs Windows-compatible ICMP ping using subprocess, extracts latency and loss
using regular expressions, and returns clean structured dictionaries.
"""
import re
import subprocess
import sys
from typing import Dict, Any, Optional


def ping_host(target: str, count: int = 1, timeout_ms: int = 1500) -> Dict[str, Any]:
    """
    Pings a target host (IP address or FQDN) using the operating system's ping command.
    Uses regex to parse latency and packet loss.

    Returns:
        dict: {
            "target": str,
            "success": bool,
            "latency_ms": Optional[float],
            "packet_loss_pct": float,
            "min_ms": Optional[float],
            "avg_ms": Optional[float],
            "max_ms": Optional[float],
            "status": str ("ONLINE", "HIGH_LATENCY", "OFFLINE"),
            "raw_output": str,
            "error": Optional[str]
        }
    """
    target = target.strip()
    result: Dict[str, Any] = {
        "target": target,
        "success": False,
        "latency_ms": None,
        "packet_loss_pct": 100.0,
        "min_ms": None,
        "avg_ms": None,
        "max_ms": None,
        "status": "OFFLINE",
        "raw_output": "",
        "error": None,
    }

    if not target:
        result["error"] = "Empty target specified"
        return result

    # Determine command based on platform (Windows primary, POSIX fallback)
    if sys.platform.startswith("win"):
        # -n = count, -w = timeout in ms
        cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), target]
    else:
        # POSIX: -c = count, -W = timeout in seconds
        timeout_sec = max(1, timeout_ms // 1000)
        cmd = ["ping", "-c", str(count), "-W", str(timeout_sec), target]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=(timeout_ms * count / 1000.0) + 3.0,
        )
        output = proc.stdout
        result["raw_output"] = output

        # 1. Parse individual packet response times
        # Examples: "time=14ms", "time<1ms", "time=0.4ms"
        times = re.findall(r"time[=<]([\d\.]+)\s*ms", output, re.IGNORECASE)
        time_values = [float(t) for t in times]

        # 2. Parse Packet Loss Percentage
        # Examples: "Lost = 0 (0% loss)", "0.0% packet loss"
        loss_match = re.search(r"\((\d+)%\s*loss\)", output, re.IGNORECASE)
        if not loss_match:
            loss_match = re.search(r"(\d+(?:\.\d+)?)%\s*packet loss", output, re.IGNORECASE)

        if loss_match:
            result["packet_loss_pct"] = float(loss_match.group(1))

        # 3. Parse Minimum, Maximum, Average summary if available
        # Example Windows: "Minimum = 14ms, Maximum = 16ms, Average = 15ms"
        min_match = re.search(r"Minimum\s*=\s*(\d+)ms", output, re.IGNORECASE)
        max_match = re.search(r"Maximum\s*=\s*(\d+)ms", output, re.IGNORECASE)
        avg_match = re.search(r"Average\s*=\s*(\d+)ms", output, re.IGNORECASE)

        if avg_match:
            result["avg_ms"] = float(avg_match.group(1))
            result["latency_ms"] = result["avg_ms"]
        elif time_values:
            # Fallback to calculating mean from individual time values
            avg_val = round(sum(time_values) / len(time_values), 2)
            result["avg_ms"] = avg_val
            result["latency_ms"] = avg_val

        if min_match:
            result["min_ms"] = float(min_match.group(1))
        elif time_values:
            result["min_ms"] = min(time_values)

        if max_match:
            result["max_ms"] = float(max_match.group(1))
        elif time_values:
            result["max_ms"] = max(time_values)

        # 4. Check for success & determine status
        if result["latency_ms"] is not None and result["packet_loss_pct"] < 100.0:
            result["success"] = True
            if result["latency_ms"] > 150.0:
                result["status"] = "HIGH_LATENCY"
            else:
                result["status"] = "ONLINE"
        else:
            result["status"] = "OFFLINE"
            if "Destination host unreachable" in output:
                result["error"] = "Destination host unreachable"
            elif "Request timed out" in output:
                result["error"] = "Request timed out"
            else:
                result["error"] = "Host failed to respond"

    except subprocess.TimeoutExpired:
        result["error"] = f"Ping process exceeded timeout ({timeout_ms}ms)"
        result["status"] = "OFFLINE"
    except Exception as e:
        result["error"] = f"Ping execution error: {str(e)}"
        result["status"] = "OFFLINE"

    return result
