"""ProjectPulse AI — Windows Background Agent with Native Tray and Desktop Window.

Features:
- Single-instance kernel file lock (msvcrt)
- 6 Accurate Statuses: Starting, Connecting, Running, Paused, Offline (Local Only), Error
- Native Desktop Window with Live Metrics, Searchable History, and Settings
- Minimizes to system tray by default (closing window hides it)
- Real development telemetry capture and local offline queue persistence
- VS Code workspace detection and Win32 user idle time tracking
- Optional start with Windows and desktop shortcut creation
"""

import logging
import os
from pathlib import Path
import threading
import time
import tkinter as tk
import webbrowser

from PIL import Image, ImageDraw
import pystray

try:
    import msvcrt
except ImportError:
    msvcrt = None

from agent.backend_client import BackendClient
from agent.collectors import CollectorManager
from agent.config import AgentConfig
from agent.desktop_window import DesktopAgentWindow
from agent.platform_integration import (
    generate_silent_launchers,
    is_autostart_enabled,
    set_autostart_with_windows,
)
from agent.session_tracker import SessionTracker
from agent.summary_popup import DeveloperSummaryPopup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

LOCK_FILE = Path(__file__).resolve().parent / "config" / ".agent.lock"


class SingleInstanceLock:
    """Kernel-level file lock ensuring only one desktop agent process runs at a time."""

    def __init__(self, lock_path: Path = LOCK_FILE):
        self.lock_path = lock_path
        self._file = None

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._file = open(self.lock_path, "a+")
            if msvcrt:
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            self._file.seek(0)
            self._file.truncate()
            self._file.write(str(os.getpid()))
            self._file.flush()
            return True
        except (IOError, OSError):
            if self._file:
                try:
                    self._file.close()
                except Exception:
                    pass
                self._file = None
            return False

    def release(self) -> None:
        if self._file:
            try:
                if msvcrt:
                    self._file.seek(0)
                    msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass


def _create_icon_image(status: str = "RUNNING") -> Image.Image:
    """Pulse icon with status color: Green=Running, Amber=Paused, Gray=Offline, Red=Error, Blue=Connecting."""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    colors = {
        "RUNNING": (16, 185, 129, 255),      # Green
        "ONLINE": (16, 185, 129, 255),       # Green
        "CONNECTING": (59, 130, 246, 255),   # Blue
        "STARTING": (245, 158, 11, 255),     # Amber
        "PAUSED": (249, 115, 22, 255),       # Orange
        "OFFLINE": (100, 116, 139, 255),     # Slate Gray
        "ERROR": (239, 68, 68, 255),         # Red
    }
    bg_color = colors.get(status, (59, 130, 246, 255))

    draw.ellipse((6, 6, 58, 58), fill=bg_color)
    draw.ellipse((20, 20, 44, 44), fill=(255, 255, 255, 255))
    return image


class TrayApp:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.backend = BackendClient(config)
        self.collectors = CollectorManager(config, self.backend)
        self.session_tracker = SessionTracker(
            approved_workspace=config.project_path,
            idle_threshold_seconds=config.idle_threshold_seconds,
            on_session_start=self._on_session_started,
            on_session_end=self._on_session_ended,
        )
        self._lock = SingleInstanceLock()
        self._icon: pystray.Icon | None = None
        self._root: tk.Tk | None = None
        self._popup: DeveloperSummaryPopup | None = None
        self._desktop_window: DesktopAgentWindow | None = None
        self._running = True
        self._status = "STARTING"
        self._last_latency_ms = 0

        # Wire up collectors event notification to session tracker
        self.collectors._on_event_sent = self._on_collector_event

        # Generate silent launchers
        generate_silent_launchers()

    def _on_collector_event(self, event) -> None:
        """Invoked whenever a collector emits an event."""
        if hasattr(event, "event_type"):
            etype = str(event.event_type)
            if "COMMIT" in etype or "PUSH" in etype:
                self.session_tracker.record_task_verification()
            else:
                self.session_tracker.record_editing_activity()

        if self._root and self._desktop_window:
            self._root.after(0, self._desktop_window.refresh_metrics)

    def _on_session_started(self, metrics: dict) -> None:
        self.backend.event_queue.save_work_session(metrics)

    def _on_session_ended(self, metrics: dict) -> None:
        self.backend.event_queue.save_work_session(metrics)

    @property
    def monitoring_menu_label(self) -> str:
        queue_count = self.backend.event_queue.pending_count
        queue_str = f" [Queue: {queue_count}]" if queue_count > 0 else ""
        if not self.config.monitoring_active:
            return f"● Status: PAUSED{queue_str}"
        return f"● Status: {self._status}{queue_str}"

    @property
    def role_menu_label(self) -> str:
        return f"● Role: {self.config.role}"

    def _dashboard_url(self) -> str:
        base = self.config.frontend_url.rstrip("/")
        role_paths = {
            "DEVELOPER": "/developer",
            "TESTER": "/tester",
            "QA": "/qa",
            "PROJECT_MANAGER": "/manager",
        }
        path = role_paths.get(self.config.role, "/developer")
        params = f"project_id={self.config.project_id}&user_id={self.config.user_id}"
        return f"{base}{path}?{params}"

    def _show_desktop_window(self) -> None:
        if self._root and self._desktop_window:
            self._root.after(0, self._desktop_window.show)

    def _show_popup(self) -> None:
        if self._root and self._popup:
            self._root.after(0, self._popup.show)

    def _on_open_dashboard(self, _icon=None, _item=None):
        webbrowser.open(self._dashboard_url())

    def set_monitoring(self, active: bool) -> None:
        if self.config.monitoring_active == active:
            return
        self.config.monitoring_active = active
        self.config.save()
        self.backend.set_monitoring_status(active)
        self.session_tracker.is_monitoring = active

        if active:
            self.collectors.restart()
            self._status = "RUNNING"
        else:
            self.collectors.stop()
            self._status = "PAUSED"

        self._refresh_state()

    def _on_pause_monitoring(self, _icon=None, _item=None):
        self.set_monitoring(False)

    def _on_resume_monitoring(self, _icon=None, _item=None):
        self.set_monitoring(True)

    def _on_exit(self, _icon=None, _item=None):
        self._running = False
        self.collectors.stop()
        self.session_tracker.stop()

        if self._desktop_window and self._root:
            self._root.after(0, self._desktop_window.hide)
        if self._popup and self._root:
            self._root.after(0, self._popup.destroy)
        if self._icon:
            self._icon.stop()
        if self._root:
            self._root.after(100, self._root.destroy)

        self._lock.release()
        logger.info("ProjectPulse Agent shutdown complete.")

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("ProjectPulse AI Desktop Agent", None, enabled=False),
            pystray.MenuItem(lambda _: self.role_menu_label, None, enabled=False),
            pystray.MenuItem(lambda _: self.monitoring_menu_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Desktop Window", lambda *_: self._show_desktop_window(), default=True),
            pystray.MenuItem("Open Web Dashboard", self._on_open_dashboard),
            pystray.MenuItem("Quick Status Popup", lambda *_: self._show_popup()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pause Monitoring",
                self._on_pause_monitoring,
                enabled=lambda _: self.config.monitoring_active,
            ),
            pystray.MenuItem(
                "Resume Monitoring",
                self._on_resume_monitoring,
                enabled=lambda _: not self.config.monitoring_active,
            ),
            pystray.MenuItem("Settings…", lambda *_: self._show_desktop_window()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Agent", self._on_exit),
        )

    def _refresh_state(self):
        if self._icon:
            self._icon.menu = self._build_menu()
            self._icon.icon = _create_icon_image(self._status)
        if self._desktop_window:
            self._desktop_window.set_status(self._status, latency_ms=self._last_latency_ms)

    def _heartbeat_and_watchdog_loop(self):
        """Dedicated background thread running 15s heartbeats and collector supervisor checks."""
        while self._running:
            try:
                t0 = time.time()
                hb_ok = self.backend.send_heartbeat()
                elapsed_ms = int((time.time() - t0) * 1000)

                if hb_ok:
                    self._last_latency_ms = elapsed_ms
                    if self.config.monitoring_active:
                        self._status = "RUNNING"
                else:
                    # Backend unreachable -> Local Only mode
                    self._last_latency_ms = 0
                    if self.config.monitoring_active:
                        self._status = "OFFLINE"

                # Check collectors
                if self.config.monitoring_active and self._status != "PAUSED":
                    if not self.collectors._collectors:
                        logger.info("Watchdog detected stopped collectors; restarting...")
                        self.collectors.start()

                # Check VS Code integration: if auto-detect enabled and workspace open
                if self.config.vscode_auto_detect and self.config.monitoring_active:
                    if self.session_tracker.is_vscode_running_for_workspace():
                        pass  # Active workspace confirmed

                # Periodic session metrics persistence
                self.backend.event_queue.save_work_session(self.session_tracker.get_metrics())

                self._refresh_state()
            except Exception as exc:
                logger.error("Watchdog loop error: %s", exc)
                self._status = "ERROR"
                self._refresh_state()

            # Sleep 15s in small increments
            for _ in range(15):
                if not self._running:
                    break
                time.sleep(1.0)

    def run(self, show_window_on_start: bool = True):
        # 1. Acquire single-instance lock
        if not self._lock.acquire():
            logger.warning("Another instance of ProjectPulse Agent is already running. Exiting.")
            print("[!] ProjectPulse Agent is already running in the system tray.")
            return

        self._root = tk.Tk()
        self._root.withdraw()
        self._root.title("ProjectPulse AI")

        # 2. Initialize desktop window
        self._desktop_window = DesktopAgentWindow(
            root=self._root,
            config=self.config,
            backend=self.backend,
            session_tracker=self.session_tracker,
            on_toggle_monitoring=self.set_monitoring,
            on_open_dashboard=self._on_open_dashboard,
            on_exit=self._on_exit,
        )

        # 3. Initialize legacy compact popup
        self._popup = DeveloperSummaryPopup(
            self._root,
            self.config,
            self.backend,
            on_open_dashboard=self._on_open_dashboard,
            on_toggle_monitoring=lambda: self.set_monitoring(not self.config.monitoring_active),
        )

        # 4. Start session tracker
        self.session_tracker.start()

        # 5. Start collectors
        if self.config.monitoring_active:
            self.collectors.start()
            self._status = "RUNNING"
        else:
            self._status = "PAUSED"

        # 6. Start supervisor & heartbeat loop
        threading.Thread(target=self._heartbeat_and_watchdog_loop, daemon=True).start()

        # 7. Start system tray icon
        self._icon = pystray.Icon(
            "ProjectPulse AI",
            _create_icon_image(self._status),
            f"ProjectPulse AI ({self.config.role})",
            menu=self._build_menu(),
        )
        threading.Thread(target=self._icon.run, daemon=True).start()
        logger.info("Tray icon started — agent is actively monitoring %s", self.config.project_path or "unconfigured folder")

        if show_window_on_start:
            self._root.after(300, self._desktop_window.show)

        self._root.mainloop()
