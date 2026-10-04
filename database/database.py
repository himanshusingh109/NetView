"""
SQLite Database Layer for NetView.
Handles database initialization, table creation, and parameterized CRUD operations.
"""
import os
import sqlite3
from typing import List, Dict, Any, Optional

# Path definitions
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "netview.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates and returns a SQLite connection with foreign keys enabled."""
    target_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes tables and indexes in the SQLite database."""
    conn = get_connection(db_path)
    try:
        with conn:
            # 1. Hosts Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hosts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT NOT NULL,
                    hostname TEXT,
                    label TEXT NOT NULL,
                    check_interval INTEGER DEFAULT 5,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ip_address, label)
                );
            """)

            # 2. Telemetry Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    latency_ms REAL,
                    status TEXT NOT NULL,
                    packet_loss REAL DEFAULT 0.0,
                    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE
                );
            """)

            # 3. Alerts Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE
                );
            """)

            # Indexes for efficient queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_host ON telemetry(host_id, timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_host ON alerts(host_id, timestamp);")
    finally:
        conn.close()


# ---------------- HOST CRUD OPERATIONS ----------------

def add_host(
    ip_address: str,
    label: str,
    hostname: Optional[str] = None,
    check_interval: int = 5,
    is_active: int = 1,
    db_path: Optional[str] = None
) -> int:
    """Inserts a new host. Returns the inserted host ID."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO hosts (ip_address, label, hostname, check_interval, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ip_address.strip(), label.strip(), hostname.strip() if hostname else None, check_interval, is_active)
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_all_hosts(active_only: bool = False, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all hosts, optionally filtering only active ones."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM hosts"
        params = []
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY id ASC"
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_host_by_id(host_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single host by ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT * FROM hosts WHERE id = ?", (host_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_host_status(host_id: int, is_active: int, db_path: Optional[str] = None) -> bool:
    """Toggles host active status (1 = active, 0 = paused)."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("UPDATE hosts SET is_active = ? WHERE id = ?", (is_active, host_id))
            return cursor.rowcount > 0
    finally:
        conn.close()


def delete_host(host_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a host and cascades deletion to telemetry and alerts."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("DELETE FROM hosts WHERE id = ?", (host_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


# ---------------- TELEMETRY OPERATIONS ----------------

def add_telemetry(
    host_id: int,
    latency_ms: Optional[float],
    status: str,
    packet_loss: float = 0.0,
    db_path: Optional[str] = None
) -> int:
    """Records a single telemetry probe for a host."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO telemetry (host_id, latency_ms, status, packet_loss)
                VALUES (?, ?, ?, ?)
                """,
                (host_id, latency_ms, status, packet_loss)
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_recent_telemetry(host_id: Optional[int] = None, limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recent telemetry entries, optionally filtered by host."""
    conn = get_connection(db_path)
    try:
        if host_id:
            query = """
                SELECT t.*, h.label AS host_label, h.ip_address
                FROM telemetry t
                JOIN hosts h ON t.host_id = h.id
                WHERE t.host_id = ?
                ORDER BY t.timestamp DESC LIMIT ?
            """
            cursor = conn.execute(query, (host_id, limit))
        else:
            query = """
                SELECT t.*, h.label AS host_label, h.ip_address
                FROM telemetry t
                JOIN hosts h ON t.host_id = h.id
                ORDER BY t.timestamp DESC LIMIT ?
            """
            cursor = conn.execute(query, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ---------------- ALERTS OPERATIONS ----------------

def add_alert(
    host_id: int,
    severity: str,
    message: str,
    db_path: Optional[str] = None
) -> int:
    """Records a triggered alert."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO alerts (host_id, severity, message)
                VALUES (?, ?, ?)
                """,
                (host_id, severity, message)
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_recent_alerts(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recent alerts with associated host details."""
    conn = get_connection(db_path)
    try:
        query = """
            SELECT a.*, h.label AS host_label, h.ip_address
            FROM alerts a
            JOIN hosts h ON a.host_id = h.id
            ORDER BY a.timestamp DESC LIMIT ?
        """
        cursor = conn.execute(query, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def seed_default_hosts_if_empty(db_path: Optional[str] = None) -> None:
    """Seeds recommended demo targets if the hosts table is currently empty."""
    hosts = get_all_hosts(db_path=db_path)
    if not hosts:
        defaults = [
            ("8.8.8.8", "Google Public DNS", "dns.google", 5),
            ("1.1.1.1", "Cloudflare DNS", "one.one.one.one", 5),
            ("google.com", "Google Web", "google.com", 10),
            ("github.com", "GitHub Web", "github.com", 10),
        ]
        for ip, label, hostname, interval in defaults:
            try:
                add_host(ip, label, hostname, interval, db_path=db_path)
            except sqlite3.IntegrityError:
                pass
