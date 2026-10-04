"""
Route Tracer (Traceroute) Module for NetView.
Executes Windows native tracert, parses hop-by-hop latency and router IPs,
and provides both batch and streaming hop discovery.
"""
import re
import subprocess
import sys
from typing import Dict, Any, List, Optional, Callable


def parse_traceroute_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single line of traceroute/tracert output.
    Returns a hop dictionary if the line represents an active hop, else None.
    """
    line = line.strip()
    # Match hop line: starts with a digit (hop number)
    hop_match = re.match(r"^(\d+)\s+(.+)$", line)
    if not hop_match:
        return None

    hop_num = int(hop_match.group(1))
    rest = hop_match.group(2)

    # Extract all round trip times (e.g. '14 ms', '<1 ms', or '*')
    rtt_matches = re.findall(r"(?:<1|\d+)\s*ms|\*", rest)

    # Extract IP address strictly:
    # IPv4: 4 octets separated by dots (e.g. 192.168.1.1)
    # IPv6: hexadecimal blocks separated by at least two colons (e.g. 2607:f8b0:...)
    ip_match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", rest)
    if not ip_match:
        ip_match = re.search(r"\b((?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}|::1)\b", rest)

    timed_out = "Request timed out" in rest or (len(rtt_matches) > 0 and all(r == "*" for r in rtt_matches))

    ip_addr = ip_match.group(1) if ip_match else ("*" if timed_out else "Unknown")

    # Calculate average response time among valid replies
    valid_ms = []
    for rtt in rtt_matches:
        if "<1" in rtt:
            valid_ms.append(0.5)
        elif "ms" in rtt:
            digits = re.search(r"(\d+)", rtt)
            if digits:
                valid_ms.append(float(digits.group(1)))

    avg_rtt = round(sum(valid_ms) / len(valid_ms), 1) if valid_ms else None

    return {
        "hop": hop_num,
        "ip": ip_addr,
        "rtt_ms": avg_rtt,
        "rtt_display": f"{avg_rtt} ms" if avg_rtt is not None else "* (Timed out)",
        "status": "RESPONDED" if not timed_out else "TIMED_OUT",
        "raw": line,
    }


def run_traceroute(
    target: str,
    max_hops: int = 15,
    timeout_ms: int = 1000,
    hop_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> Dict[str, Any]:
    """
    Executes a traceroute against the target.
    Can emit hops dynamically through hop_callback if provided.

    Returns:
        dict: {
            "target": str,
            "success": bool,
            "hops": List[Dict[str, Any]],
            "total_hops": int,
            "error": Optional[str]
        }
    """
    target = target.strip()
    result: Dict[str, Any] = {
        "target": target,
        "success": False,
        "hops": [],
        "total_hops": 0,
        "error": None,
    }

    if not target:
        result["error"] = "Target cannot be empty"
        return result

    # Build command based on OS
    if sys.platform.startswith("win"):
        # -d: do not resolve addresses to hostnames (much faster)
        # -h: maximum hops
        # -w: timeout in ms
        cmd = ["tracert", "-d", "-h", str(max_hops), "-w", str(timeout_ms), target]
    else:
        # Linux/macOS fallback: traceroute -n -m <max_hops> -w <timeout_sec>
        timeout_sec = max(1, timeout_ms // 1000)
        cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", str(timeout_sec), target]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        hops: List[Dict[str, Any]] = []

        if proc.stdout:
            for line in iter(proc.stdout.readline, ""):
                if stop_check and stop_check():
                    proc.terminate()
                    break

                hop_data = parse_traceroute_line(line)
                if hop_data:
                    hops.append(hop_data)
                    if hop_callback:
                        hop_callback(hop_data)

        proc.stdout.close()
        proc.wait(timeout=5)

        result["hops"] = hops
        result["total_hops"] = len(hops)
        result["success"] = len(hops) > 0

    except Exception as e:
        result["error"] = f"Traceroute error: {str(e)}"

    return result
