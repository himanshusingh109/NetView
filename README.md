# NetView – Network Monitoring and Diagnostic System

NetView is a Python Tkinter desktop application for monitoring network hosts, diagnosing connectivity, recording telemetry, generating threshold-based alerts, and exporting historical reports. It provides network administrators, students, and engineers with an integrated environment to observe host health, analyze latency, and perform essential diagnostic benchmarks without toggling between multiple terminal tools. Built exclusively using the Python standard library, NetView balances a responsive graphical interface with multithreaded network workers and persistent SQLite storage.

---

## 1. Problem Statement

Basic network troubleshooting often requires multiple command-line utilities such as `ping`, `nslookup`, and `tracert`. While functional, these terminal tools lack a unified interface for:
- Monitoring multiple hosts concurrently.
- Viewing live round-trip latency and availability metrics.
- Tracking historical performance results over time.
- Detecting high latency and offline conditions automatically.
- Performing common diagnostic benchmarks in one place.

NetView combines these capabilities into a single, cohesive Tkinter desktop application.

---

## 2. Motivation

NetView was developed as an educational yet practical software engineering project to demonstrate core computer networking and software architecture principles in Python. The project focuses on:
- Learning and applying Python networking concepts, including socket communication, ICMP reachability, and DNS resolution.
- Combining a desktop Tkinter graphical user interface with asynchronous networking operations.
- Applying multithreading and thread synchronization to maintain interface responsiveness.
- Using an embedded SQLite database for structured data persistence.
- Creating a practical, production-quality desktop tool suitable for everyday network observation.
- Demonstrating key computer science concepts from the academic Python syllabus in a real-world application.

---

## 3. Objectives

- **Monitor Network Hosts Periodically:** Automate background availability checks and round-trip time (RTT) measurements for user-defined IP addresses and domain names.
- **Display Live Latency and Status:** Present real-time telemetry updates and interactive latency visual representations via a custom Tkinter Canvas graph.
- **Detect Offline and High-Latency Conditions:** Automatically evaluate observed metrics against performance thresholds and trigger alert notifications.
- **Perform Diagnostic Utilities:** Provide on-demand ICMP ping tests, forward and reverse DNS lookups, hop-by-hop Windows route tracing, and TCP echo benchmarks.
- **Demonstrate Client/Server Communication:** Implement a dedicated local TCP Echo Server and Client to test transport-layer connectivity and payload integrity.
- **Store Telemetry and Alerts in SQLite:** Maintain structured relational records for targets, periodic measurements, and alert incidents.
- **View Historical Records:** Allow users to filter, inspect, and audit historical telemetry and alert logs directly in the user interface.
- **Export Reports as CSV and JSON:** Provide data export options for external analysis and record-keeping.
- **Maintain a Responsive Interface:** Ensure the main Tkinter thread remains completely fluid by delegating all blocking I/O operations to daemon worker threads.

---

## 4. Key Features

### Dashboard
- **Local Hostname & Local IP:** Discovers and displays the local machine hostname and active private IPv4 address.
- **Default Gateway Detection:** Identifies the active local network gateway address.
- **Internet Reachability:** Provides continuous confirmation of external internet connectivity.
- **Fleet KPI Metrics:** Displays summary counts for total hosts, online nodes, offline nodes, and active alerts.
- **Recent Activity Feed:** Presents a live stream of recent monitoring and diagnostic events.

### Host Monitor
- **Host Fleet Management:** Add, configure, and remove monitored targets with custom labels and polling intervals.
- **Flexible Polling Controls:** Start, pause, resume, and stop monitoring cycles dynamically.
- **Real-Time Latency Graph:** Custom Tkinter Canvas rolling line graph rendering live latency trends for selected hosts.
- **Statistical Aggregates:** Real-time calculation and display of minimum, maximum, and average latency metrics.
- **Current Status Badges:** Visual indicators reflecting host status (e.g., Online, Warning, Critical, Offline).

### Diagnostics
- **Direct ICMP Ping:** Configurable packet count and timeout with latency statistics and packet loss calculations.
- **DNS Forward Lookup:** Resolves fully qualified domain names (FQDN) to IPv4 addresses.
- **DNS Reverse Lookup:** Resolves IP addresses back to canonical hostnames.
- **Windows Traceroute:** Hop-by-hop route tracing leveraging the Windows `tracert` utility with real-time hop streaming and auto-scrolling.
- **TCP Echo Client/Server Benchmark:** Built-in TCP Echo Server and Client testing port responsiveness, round-trip time (RTT), and end-to-end payload integrity verification.

### History & Reports
- **Telemetry History Explorer:** Tabular inspection of historical ping measurements, timestamps, and packet loss rates.
- **Alert History Viewer:** Comprehensive log of warning, critical, and recovery events with root cause summaries.
- **Host & Status Filtering:** Dynamic filtering by host identifier and operational status.
- **CSV Export:** Tabular data export of telemetry and alert logs to comma-separated values format.
- **JSON Export:** Structured data export of historical records for automated ingestion or archiving.

---

## 5. System Architecture

NetView utilizes a decoupled multi-tier architecture designed to keep the graphical interface fully responsive while network I/O and database operations run in the background.

```
Tkinter GUI (Main Thread)
    ↓
queue.Queue (Thread-Safe Event Channel)
    ↓
Background Services / Diagnostic Threads
    ↓
Network Layer (Sockets, Subprocess, DNS)
    ↓
SQLite Database (Persistent Storage)
```

- **Tkinter GUI:** Runs strictly on the main application thread, managing user interactions, widget rendering, and scheduled updates.
- **queue.Queue:** Acts as the thread-safe bridge transferring results, status changes, and metrics from background threads safely to the GUI.
- **Background Services & Diagnostic Threads:** Execute network checks, threshold evaluations, and long-running diagnostic tasks within background daemon threads so user interactions are never blocked.
- **Network Layer:** Interfaces with operating system networking tools and Python `socket` APIs for ICMP pinging, DNS queries, route tracing, and TCP benchmarking.
- **SQLite Database:** Provides structured, ACID-compliant persistence for host configurations, time-series telemetry data, and generated alerts.

---

## 6. Project Structure

```
NetView/
├── main.py
├── README.md
├── .gitignore
├── data/
│   └── .gitkeep
├── gui/
│   ├── __init__.py
│   ├── dashboard.py
│   ├── monitor.py
│   ├── diagnostics.py
│   └── history.py
├── network/
│   ├── __init__.py
│   ├── ping.py
│   ├── dns.py
│   ├── traceroute.py
│   └── client_server.py
├── database/
│   ├── __init__.py
│   └── database.py
├── services/
│   ├── __init__.py
│   ├── monitor_service.py
│   ├── alert_service.py
│   └── export_service.py
├── models/
│   ├── __init__.py
│   └── models.py
├── test_phase2.py
├── test_phase3.py
└── test_phase4.py
```

---

## 7. Technologies Used

| Technology | Purpose |
| :--- | :--- |
| **Python** | Core programming language |
| **Tkinter / ttk** | Desktop graphical user interface components |
| **SQLite3** | Embedded relational database for persistent storage |
| **threading** | Background network monitoring and non-blocking diagnostic execution |
| **queue** | Thread-safe inter-thread communication between workers and the GUI |
| **socket** | Low-level TCP client/server communication and DNS resolution |
| **subprocess** | Execution of Windows `ping` and `tracert` commands |
| **re** | Regular expression parsing of network diagnostic outputs |
| **csv** | CSV report generation for historical exports |
| **json** | JSON report generation for structured telemetry exports |

> **Note:** No external Python packages are required. NetView runs entirely on standard Python distributions.

---

## 8. Database Design

NetView utilizes an embedded SQLite database (`data/netview.db`) structured across three application tables:

### `hosts`
Stores user-configured target nodes and monitoring preferences. Fields include host ID, IP address or hostname, descriptive label, check interval in seconds, active status, and creation timestamp.

### `telemetry`
Stores timestamped network monitoring results. Fields include measurement ID, foreign key reference to the host, response latency (minimum, average, maximum in milliseconds), packet loss percentage, status string, and measurement timestamp.

### `alerts`
Stores threshold and incident events. Fields include alert ID, foreign key reference to the host, severity level (`WARNING` or `CRITICAL`), trigger message, timestamp, and resolution status.

### Relational Integrity
- **Foreign Keys:** Enabled via `PRAGMA foreign_keys = ON` to enforce referential consistency across hosts, telemetry, and alerts.
- **Cascading Deletion:** Deleting a host automatically removes its associated telemetry entries and alert logs.
- **Parameterized SQL:** All queries use parameterized placeholders (`?`) to prevent query corruption and ensure reliable data handling.

---

## 9. Multithreading and Event Handling

Network operations like ICMP pinging, DNS lookups, and route tracing are inherently blocking. NetView enforces strict architectural boundaries to preserve UI responsiveness:

- Each monitored host can have an independent background daemon worker thread.
- Diagnostic tasks (such as traceroute and TCP echo testing) are spawned in dedicated background threads.
- Worker threads perform network checks, persist metrics directly to the SQLite database, and place structured event payloads into a thread-safe `queue.Queue`.
- The Tkinter main thread periodically polls the event queue using scheduled `root.after()` callbacks.
- The main thread unpacks incoming events, updates status labels, refreshes Treeview tables, and redraws the latency Canvas graph.

> **Important:** Tkinter widgets are not updated directly from worker threads. All UI rendering occurs exclusively on the Tkinter main thread.

---

## 10. Alert System

NetView includes an integrated threshold monitoring engine that analyzes latency and availability metrics from every telemetry check:

- **WARNING Alert:** Generated when observed round-trip latency exceeds **150 ms**.
- **CRITICAL Alert:** Generated when observed round-trip latency exceeds **300 ms** or when a host becomes completely **OFFLINE** (100% packet loss).
- **Duplicate Suppression:** The alert service tracks current host state and suppresses repetitive identical alerts during sustained high-latency or offline conditions.
- **Recovery Events:** When a previously degraded or offline host returns to normal operating parameters (< 150 ms and reachable), the system automatically emits a recovery notification and clears the incident.

---

## 11. Installation & Requirements

### System Requirements
- **Python Version:** Python 3.10 or higher.
- **Operating System:** Windows recommended because route tracing utilizes the Windows `tracert` utility.
- **Tkinter:** Tkinter must be available with your Python installation (included by default in standard Windows Python distributions).
- **Dependencies:** No external dependencies or `pip` installations are required.

### Running the Application
From the NetView project directory, run:

```bash
python main.py
```

---

## 12. Testing

NetView has been validated through automated test suites and end-to-end interactive quality assurance:

### Automated Test Suites
- **Phase 2 (Network & Database Layer):**
  ```bash
  python test_phase2.py
  ```
  *Result: 7/7 tests passed.* Validates database schema creation, CRUD operations, ICMP ping parsing, DNS forward/reverse resolution, traceroute parsing, and TCP echo client/server benchmarks.

- **Phase 3 (Services & Alerting Layer):**
  ```bash
  python test_phase3.py
  ```
  *Result: 10/10 tests passed.* Validates multi-host monitoring threads, thread-safe queue event delivery, threshold alert triggers, alert deduplication, and CSV/JSON report exports.

- **Phase 4 (Tkinter GUI Integration):**
  ```bash
  python test_phase4.py
  ```
  *Result: 11/11 tests passed.* Validates queue integration with Tkinter, widget event dispatching, thread-safe Canvas graph rendering, and tabular history filtering.

### Interactive End-to-End QA
A comprehensive interactive QA audit was conducted on the running application, verifying:
- Clean application startup and window geometry.
- Dashboard interface discovery, KPI counter accuracy, and internet reachability checks.
- Host monitoring lifecycle: adding hosts, dynamic polling, pausing, resuming, and stopping.
- Real-time Canvas latency graph rendering and rolling history updates.
- Direct ICMP pinging, forward and reverse DNS queries, and Windows traceroute auto-scrolling.
- TCP Echo Server start/stop handling and Echo Client round-trip latency and integrity validation.
- Telemetry and alert history filtering and export to both CSV and JSON formats.
- Persistent state retention in SQLite across full application restarts.

---

## 13. Results

The completed NetView system delivers a robust, responsive desktop solution for network observability:
- **Responsive Background Monitoring:** Concurrently monitors multiple network targets without interface freezing, lag, or thread contention.
- **Telemetry Persistence:** Reliably records timestamped latency metrics, packet loss statistics, and reachability statuses in SQLite.
- **Automated Alerts:** Accurately detects latency degradation and offline events with duplicate suppression and recovery notifications.
- **Integrated Diagnostics:** Provides immediate ping, DNS, traceroute, and TCP echo diagnostics from a unified desktop interface.
- **Historical Analysis & Export:** Enables operators to inspect historical trends and export data to standard CSV and JSON formats.
- **Clean Lifecycle & Persistence:** Demonstrates safe shutdown of all background worker threads and complete state persistence across sessions.

---

## 14. Python Syllabus Mapping

| Syllabus Requirement | How It Is Exercised in NetView |
| :--- | :--- |
| **Python Fundamentals** | Data typing, string formatting, arithmetic latency computations |
| **Conditions and Loops** | Monitor polling cycles, threshold branches, hop-by-hop traceroute iteration |
| **Functions** | Event handlers, diagnostic helper routines, queue processing callbacks |
| **Collections** | Lists, dictionaries, tuples, and `deque` for rolling graph buffers |
| **Modules & Packages** | Structured package hierarchy (`gui`, `network`, `database`, `services`, `models`) |
| **Regular Expressions** | Parsing command-line outputs for ping statistics and IP addresses (`re` module) |
| **Object-Oriented Programming** | Encapsulated classes for models, services, network drivers, and GUI components |
| **Inheritance & Polymorphism** | View components inheriting from `ttk.Frame` with unified lifecycle methods |
| **Exception Handling** | Granular handling of `socket.timeout`, `socket.error`, `sqlite3.Error`, and `subprocess.SubprocessError` |
| **File Handling** | Generating structured reports using `csv` and `json` standard modules |
| **Database Programming** | SQLite schema creation, CRUD operations, foreign key constraints, and parameterized queries |
| **Tkinter GUI** | Multi-tab `ttk.Notebook`, `Treeview` tables, entry forms, buttons, and `Canvas` |
| **Event-Driven Programming** | Button click bindings, tree selection events, and scheduled `root.after()` loops |
| **Multithreading** | Background worker threads decoupled using thread-safe `queue.Queue` |
| **Networking** | Socket connections, DNS queries, ICMP ping checks, and route tracing |
| **Client/Server Programming** | Custom multithreaded TCP Echo Server and Client benchmark utility |

---

## 15. Future Scope

While NetView fulfills all design goals for its academic and operational scope, practical future enhancements could include:
- **More Advanced Network Visualization:** Topology diagrams representing local subnet layouts and gateway hierarchies.
- **Additional Notification Mechanisms:** Desktop operating system toast notifications or sound alerts for critical incidents.
- **Cross-Platform Traceroute Support:** Adaptive shell execution supporting Linux and macOS `traceroute` syntax alongside Windows `tracert`.
- **More Configurable Monitoring Policies:** Customizable per-host latency thresholds, packet loss tolerances, and retry counts.
- **Additional Report Formats:** Exporting formatted summary reports in HTML or PDF formats.

---

## 16. Conclusion

NetView demonstrates how Python's standard library can be leveraged to build a complete, professional desktop application. By integrating Tkinter for the presentation layer, SQLite for structured data persistence, multithreading for non-blocking network I/O, and socket/subprocess programming for diagnostic operations, the project provides a comprehensive and practical demonstration of core software engineering and network programming principles.

---

## 17. Authors

Developed as an academic Python project.
