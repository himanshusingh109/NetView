# GUI package initialization
from .dashboard import DashboardTab
from .monitor import MonitorTab
from .diagnostics import DiagnosticsTab
from .history import HistoryTab

__all__ = ["DashboardTab", "MonitorTab", "DiagnosticsTab", "HistoryTab"]
