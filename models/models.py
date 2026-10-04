"""
Data models for NetView: Host, Telemetry, and Alert entities.
(To be populated during database and business logic phases)
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Host:
    id: Optional[int]
    ip_address: str
    hostname: Optional[str]
    label: str
    check_interval: int = 5
    is_active: bool = True
    created_at: Optional[str] = None


@dataclass
class Telemetry:
    id: Optional[int]
    host_id: int
    timestamp: str
    latency_ms: Optional[float]
    status: str
    packet_loss: float = 0.0


@dataclass
class Alert:
    id: Optional[int]
    host_id: int
    timestamp: str
    severity: str
    message: str
