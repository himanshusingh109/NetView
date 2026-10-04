"""
DNS Resolution Module for NetView.
Performs forward DNS lookups (Domain -> IPs) and reverse DNS lookups (IP -> Hostname)
using Python standard library socket functions with clean error handling.
"""
import socket
from typing import Dict, Any, List


def forward_lookup(domain: str) -> Dict[str, Any]:
    """
    Performs forward DNS resolution for a domain name.

    Returns:
        dict: {
            "query": str,
            "success": bool,
            "canonical_name": str,
            "ipv4_addresses": List[str],
            "ipv6_addresses": List[str],
            "error": Optional[str]
        }
    """
    domain = domain.strip()
    result: Dict[str, Any] = {
        "query": domain,
        "success": False,
        "canonical_name": "",
        "ipv4_addresses": [],
        "ipv6_addresses": [],
        "error": None,
    }

    if not domain:
        result["error"] = "Domain name cannot be empty"
        return result

    try:
        # 1. Primary lookup via getaddrinfo (captures both IPv4 and IPv6)
        addr_info = socket.getaddrinfo(domain, None)
        ipv4_set = set()
        ipv6_set = set()

        for family, _, _, canonname, sockaddr in addr_info:
            if canonname and not result["canonical_name"]:
                result["canonical_name"] = canonname
            ip = sockaddr[0]
            if family == socket.AF_INET:
                ipv4_set.add(ip)
            elif family == socket.AF_INET6:
                ipv6_set.add(ip)

        result["ipv4_addresses"] = sorted(list(ipv4_set))
        result["ipv6_addresses"] = sorted(list(ipv6_set))

        # 2. Supplementary lookup for hostname alias
        try:
            hostname, aliases, _ = socket.gethostbyname_ex(domain)
            if not result["canonical_name"]:
                result["canonical_name"] = hostname
        except Exception:
            pass

        if not result["canonical_name"]:
            result["canonical_name"] = domain

        result["success"] = True

    except socket.gaierror as e:
        result["error"] = f"DNS resolution failed: {e.strerror or 'Host not found'}"
    except Exception as e:
        result["error"] = f"Resolution error: {str(e)}"

    return result


def reverse_lookup(ip_address: str) -> Dict[str, Any]:
    """
    Performs reverse DNS (PTR) lookup for an IP address.

    Returns:
        dict: {
            "query": str,
            "success": bool,
            "hostname": str,
            "aliases": List[str],
            "error": Optional[str]
        }
    """
    ip_address = ip_address.strip()
    result: Dict[str, Any] = {
        "query": ip_address,
        "success": False,
        "hostname": "",
        "aliases": [],
        "error": None,
    }

    if not ip_address:
        result["error"] = "IP address cannot be empty"
        return result

    try:
        hostname, aliases, _ = socket.gethostbyaddr(ip_address)
        result["hostname"] = hostname
        result["aliases"] = aliases
        result["success"] = True
    except socket.herror as e:
        result["error"] = f"Reverse lookup failed: {e.strerror or 'Unknown host'}"
    except (socket.gaierror, ValueError) as e:
        result["error"] = f"Invalid IP address format: {str(e)}"
    except Exception as e:
        result["error"] = f"Reverse lookup error: {str(e)}"

    return result
