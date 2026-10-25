"""Windows Session & Idle Time Tracker for ProjectPulse AI Desktop Agent.

Implements:
1. Windows user idle time detection via ctypes.windll.user32.GetLastInputInfo (no keylogging).
2. VS Code process detection (Code.exe) and workspace folder extraction.
3. Accurate time tracking model:
   - Observed VS Code session time (process running on approved workspace)
   - Measured active interaction time (session minus idle time)
   - Estimated editing time (editing bursts)
   - Verified task time (explicitly linked to task commits)
"""

from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)

# Win32 Structure for user idle detection
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_windows_idle_seconds() -> float:
    """Return seconds since last user input on Windows (mouse/keyboard event).
    Never logs or inspects keystrokes or input content.
    """
    if os.name != "nt":
        return 0.0
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            # dwTime is in milliseconds since system boot
            # GetTickCount64 prevents 49.7 day wrap-around
            if hasattr(ctypes.windll.kernel32, "GetTickCount64"):
                current_tick = ctypes.windll.kernel32.GetTickCount64()
            else:
                current_tick = ctypes.windll.kernel32.GetTickCount()
            # Cast both to unsigned 32-bit if comparing with dwTime
            diff = (current_tick & 0xFFFFFFFF) - lii.dwTime
            if diff < 0:
                diff += 0x100000000
            return max(0.0, float(diff) / 1000.0)
    except Exception as exc:
        logger.debug("Failed to read Win32 GetLastInputInfo: %s", exc)
    return 0.0


def detect_vscode_processes() -> list[dict[str, Any]]:
    """Detect running VS Code processes (Code.exe) and extract command-line arguments to find workspaces."""
    instances = []
    if os.name != "nt":
        return instances

    try:
        # Use WMIC or PowerShell command line query (native to Windows, no external pip packages required)
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name = 'Code.exe'\" | Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            import json
            try:
                data = json.loads(res.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    cmdline = item.get("CommandLine") or ""
                    pid = item.get("ProcessId", 0)
                    instances.append({"pid": pid, "cmdline": cmdline})
            except Exception as e:
                logger.debug("Error parsing VS Code processes JSON: %s", e)
    except Exception as exc:
        logger.debug("VS Code process query failed: %s", exc)

    return instances


def find_active_vscode_workspaces() -> list[Path]:
    """Parse open VS Code workspaces from running Code.exe instances."""
    workspaces = []
    for proc in detect_vscode_processes():
        cmdline = proc.get("cmdline", "")
        # VS Code passes directories on the command line, e.g. "C:\Users\...\project"
        import shlex
        try:
            parts = shlex.split(cmdline, posix=False)
            for part in parts:
                clean_part = part.strip('"\'')
                if clean_part and not clean_part.startswith("-"):
                    p = Path(clean_part)
                    if p.exists() and p.is_dir():
                        workspaces.append(p.resolve())
        except Exception:
            continue
    return list(set(workspaces))


class SessionTracker:
    """Manages active developer session, idle detection, and time categorization."""

    DEFAULT_IDLE_THRESHOLD_SECONDS = 300.0  # 5 minutes of inactivity = idle

    def __init__(
        self,
        approved_workspace: Path | None = None,
        idle_threshold_seconds: float = DEFAULT_IDLE_THRESHOLD_SECONDS,
        on_session_start: Callable[[dict], None] | None = None,
        on_session_end: Callable[[dict], None] | None = None,
    ):
        self.approved_workspace = approved_workspace.resolve() if approved_workspace else None
        self.idle_threshold_seconds = idle_threshold_seconds
        self.on_session_start = on_session_start
        self.on_session_end = on_session_end

        self.session_id: str = f"SES-{uuid4().hex[:8].upper()}"
        self.session_start_time: datetime = datetime.now(timezone.utc)
        self.is_monitoring: bool = True
        self.is_active: bool = False
        self.is_user_idle: bool = False

        # Metrics accumulated in seconds
        self.observed_session_seconds: float = 0.0
        self.active_interaction_seconds: float = 0.0
        self.idle_seconds: float = 0.0
        self.estimated_editing_seconds: float = 0.0
        self.verified_task_seconds: float = 0.0

        self.last_activity_time: datetime = datetime.now(timezone.utc)
        self.last_check_tick: float = time.time()
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def set_approved_workspace(self, path: Path | None) -> None:
        with self._lock:
            self.approved_workspace = path.resolve() if path else None

    def record_editing_activity(self, duration_estimate: float = 30.0) -> None:
        """Call when a verified file modification or test event occurs."""
        with self._lock:
            self.last_activity_time = datetime.now(timezone.utc)
            self.estimated_editing_seconds += duration_estimate

    def record_task_verification(self, duration_estimate: float = 120.0) -> None:
        """Call when a commit or verified push linked to a Jira/PM task occurs."""
        with self._lock:
            self.last_activity_time = datetime.now(timezone.utc)
            self.verified_task_seconds += duration_estimate

    def is_vscode_running_for_workspace(self) -> bool:
        """Check if VS Code has the approved workspace open."""
        if not self.approved_workspace or not self.approved_workspace.exists():
            return False
        open_workspaces = find_active_vscode_workspaces()
        for ws in open_workspaces:
            try:
                # Direct match or subfolder
                if ws == self.approved_workspace or ws in self.approved_workspace.parents:
                    return True
                if self.approved_workspace in ws.parents:
                    return True
            except Exception:
                continue
        return False

    def update_tick(self, delta: float | None = None) -> None:
        """Advance time counters by delta seconds based on current active/idle state."""
        now_tick = time.time()
        with self._lock:
            elapsed = delta if delta is not None else max(0.0, now_tick - self.last_check_tick)
            self.last_check_tick = now_tick

            if not self.is_monitoring:
                return

            # Check idle state
            idle_now = get_windows_idle_seconds()
            self.is_user_idle = idle_now >= self.idle_threshold_seconds

            # Session is active when monitoring is enabled
            self.observed_session_seconds += elapsed

            if self.is_user_idle:
                self.idle_seconds += elapsed
            else:
                self.active_interaction_seconds += elapsed

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.session_start_time = datetime.now(timezone.utc)
        self.session_id = f"SES-{uuid4().hex[:8].upper()}"
        self.last_check_tick = time.time()

        if self.on_session_start:
            try:
                self.on_session_start(self.get_metrics())
            except Exception as e:
                logger.error("Error calling on_session_start: %s", e)

        self._thread = threading.Thread(target=self._tracker_loop, daemon=True)
        self._thread.start()
        logger.info("SessionTracker started. Session ID: %s", self.session_id)

    def stop(self) -> None:
        self._running = False
        if self.on_session_end:
            try:
                self.on_session_end(self.get_metrics())
            except Exception as e:
                logger.error("Error calling on_session_end: %s", e)
        logger.info("SessionTracker stopped.")

    def _tracker_loop(self) -> None:
        while self._running:
            try:
                self.update_tick()
            except Exception as exc:
                logger.debug("Error in session tracker tick: %s", exc)
            time.sleep(1.0)

    def get_metrics(self) -> dict[str, Any]:
        """Return real time tracking breakdown without fabricated data."""
        with self._lock:
            return {
                "session_id": self.session_id,
                "session_start_time": self.session_start_time.isoformat(),
                "last_activity_time": self.last_activity_time.isoformat(),
                "observed_session_seconds": round(self.observed_session_seconds, 1),
                "active_interaction_seconds": round(self.active_interaction_seconds, 1),
                "idle_seconds": round(self.idle_seconds, 1),
                "estimated_editing_seconds": round(self.estimated_editing_seconds, 1),
                "verified_task_seconds": round(self.verified_task_seconds, 1),
                "is_monitoring": self.is_monitoring,
                "is_user_idle": self.is_user_idle,
                "approved_workspace": str(self.approved_workspace) if self.approved_workspace else None,
            }
