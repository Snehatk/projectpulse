"""Project file watcher — detects VS Code / IDE file activity within allowlist."""

import logging
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from uuid import uuid4

from agent.ast_analyzer import (
    diff_symbols,
    extract_python_symbols,
    generate_deterministic_explanation,
)
from agent.collectors.base import BaseCollector
from shared.events import EventSource, EventType

logger = logging.getLogger(__name__)

# Directories never monitored — reduces noise and protects cache/build artifacts
IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".idea",
    ".vs",
    "data",
    ".cursor",
}

# File extensions / names to skip
IGNORED_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".tmp",
    ".swp",
    ".swo",
    ".log",
    ".db",
    ".sqlite",
    ".sqlite3",
}

IGNORED_FILE_NAMES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
}


def _file_type(path: Path) -> str:
    suffix = path.suffix
    return suffix.lstrip(".").lower() if suffix else "unknown"


def _relative_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _should_ignore(path: Path) -> bool:
    parts_lower = {p.lower() for p in path.parts}
    if parts_lower & {d.lower() for d in IGNORED_DIR_NAMES}:
        return True
    if path.name.lower() in IGNORED_FILE_NAMES:
        return True
    if path.suffix.lower() in IGNORED_FILE_SUFFIXES:
        return True
    return False


class _ProjectEventHandler(FileSystemEventHandler):
    """Handles filesystem events inside the configured project folder with Change Intelligence."""

    DEBOUNCE_SECONDS = 2.0
    COALESCE_WINDOW_SECONDS = 3.5

    def __init__(self, collector: "ProjectFileWatcherCollector"):
        self.collector = collector
        self._seen_files: set[str] = set()
        self._last_modified: dict[str, float] = {}
        self._symbol_cache: dict[str, dict] = {}
        self._pending_change_files: set[tuple[Path, str]] = set()
        self._coalesce_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._baseline_scan()

    def _baseline_scan(self) -> None:
        """Baseline scan of existing project files to index AST symbols locally without uploading source."""
        root = self.collector.config.project_path
        if not root or not root.exists():
            return
        try:
            for py_path in root.rglob("*.py"):
                if py_path.is_file() and not _should_ignore(py_path):
                    rel = _relative_path(py_path, root)
                    try:
                        content = py_path.read_text(encoding="utf-8", errors="ignore")
                        self._symbol_cache[rel] = extract_python_symbols(content)
                        self._seen_files.add(rel)
                    except Exception:
                        pass
            logger.info("Change Intelligence: Indexed baseline symbols across %d files", len(self._symbol_cache))
        except Exception as exc:
            logger.debug("Baseline scan encountered error: %s", exc)

    def _resolve(self, src_path: str) -> Path | None:
        path = Path(src_path)
        if not path.is_file():
            return None
        if _should_ignore(path):
            return None
        if not self.collector.privacy_filter.allow_path(path):
            return None
        return path

    def _debounced(self, rel_path: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last_modified.get(rel_path, 0)
            if now - last < self.DEBOUNCE_SECONDS:
                return True
            self._last_modified[rel_path] = now
            return False

    def _queue_changeset(self, path: Path, rel_path: str) -> None:
        with self._lock:
            self._pending_change_files.add((path, rel_path))
            if self._coalesce_timer and self._coalesce_timer.is_alive():
                self._coalesce_timer.cancel()
            self._coalesce_timer = threading.Timer(self.COALESCE_WINDOW_SECONDS, self._emit_coalesced_changeset)
            self._coalesce_timer.daemon = True
            self._coalesce_timer.start()

    def _emit_coalesced_changeset(self) -> None:
        with self._lock:
            pending = list(self._pending_change_files)
            self._pending_change_files.clear()

        if not pending:
            return

        rel_paths = [rel for _, rel in pending]
        all_added = []
        all_modified = []
        all_removed = []

        for p, rel in pending:
            if p.suffix == ".py" and p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    new_symbols = extract_python_symbols(content)
                    old_symbols = self._symbol_cache.get(rel, {})
                    diff = diff_symbols(old_symbols, new_symbols)
                    all_added.extend(diff["added"])
                    all_modified.extend(diff["modified"])
                    all_removed.extend(diff["removed"])
                    self._symbol_cache[rel] = new_symbols
                except Exception as exc:
                    logger.debug("Failed AST diff for %s: %s", rel, exc)

        symbol_diff_summary = {
            "added": all_added,
            "modified": all_modified,
            "removed": all_removed,
        }

        explanation = generate_deterministic_explanation(
            files_changed=rel_paths,
            symbol_diffs=symbol_diff_summary,
        )

        changeset_id = f"CS-{uuid4().hex[:8].upper()}"
        title = f"ChangeSet ({len(rel_paths)} file{'s' if len(rel_paths) > 1 else ''}): {explanation['what']}"

        metadata = {
            "changeset_id": changeset_id,
            "files_changed": rel_paths,
            "symbols_added": [s["name"] for s in all_added],
            "symbols_modified": [s["name"] for s in all_modified],
            "symbols_removed": [s["name"] for s in all_removed],
            "classification": explanation["primary_classification"],
            "explanation": explanation,
            "project": self.collector.config.project_name,
        }

        evt = self.collector.normalizer.normalize(
            source=EventSource.FILE,
            event_type=EventType.CHANGE_SET,
            title=title,
            description=explanation["what"],
            status="INFO",
            metadata=metadata,
        )
        self.collector.emit(evt)
        logger.info("Change Intelligence emitted changeset %s (%s)", changeset_id, explanation["what"])

    def _emit_file_opened(self, path: Path, rel_path: str) -> None:
        file_type = _file_type(path)
        event = self.collector.normalizer.normalize(
            source=EventSource.VS_CODE,
            event_type=EventType.FILE_OPENED,
            title=f"Opened {rel_path}",
            description=f"File accessed in project: {rel_path}",
            metadata={
                "file": rel_path,
                "file_type": file_type,
                "project": self.collector.config.project_name,
            },
        )
        self.collector.emit(event)

    def _emit_file_modified(self, path: Path, rel_path: str) -> None:
        file_type = _file_type(path)
        event = self.collector.normalizer.normalize(
            source=EventSource.VS_CODE,
            event_type=EventType.FILE_MODIFIED,
            title=f"Modified {rel_path}",
            description=f"File modified in project: {rel_path}",
            metadata={
                "file": rel_path,
                "file_type": file_type,
                "project": self.collector.config.project_name,
            },
        )
        self.collector.emit(event)
        self._queue_changeset(path, rel_path)

    def _emit_file_created(self, path: Path, rel_path: str) -> None:
        file_type = _file_type(path)
        event = self.collector.normalizer.normalize(
            source=EventSource.VS_CODE,
            event_type=EventType.FILE_CREATED,
            title=f"Created {rel_path}",
            description=f"File created in project: {rel_path}",
            metadata={
                "file": rel_path,
                "file_type": file_type,
                "project": self.collector.config.project_name,
            },
        )
        self.collector.emit(event)
        self._queue_changeset(path, rel_path)

    def _emit_file_deleted(self, rel_path: str) -> None:
        event = self.collector.normalizer.normalize(
            source=EventSource.VS_CODE,
            event_type=EventType.FILE_DELETED,
            title=f"Deleted {rel_path}",
            description=f"File deleted from project: {rel_path}",
            metadata={
                "file": rel_path,
                "project": self.collector.config.project_name,
            },
        )
        self.collector.emit(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = self._resolve(event.src_path)
        if path is None:
            return

        project_root = self.collector.config.project_path
        if project_root is None:
            return

        rel_path = _relative_path(path, project_root)
        if self._debounced(rel_path):
            return

        with self._lock:
            is_first_seen = rel_path not in self._seen_files
            if is_first_seen:
                self._seen_files.add(rel_path)

        if is_first_seen:
            self._emit_file_opened(path, rel_path)

        self._emit_file_modified(path, rel_path)
        logger.debug("FILE_MODIFIED: %s", rel_path)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = self._resolve(event.src_path)
        if path is None:
            return

        project_root = self.collector.config.project_path
        if project_root is None:
            return

        rel_path = _relative_path(path, project_root)
        with self._lock:
            if rel_path in self._seen_files:
                return
            self._seen_files.add(rel_path)

        self._emit_file_created(path, rel_path)
        logger.debug("FILE_CREATED: %s", rel_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _should_ignore(path):
            return
        project_root = self.collector.config.project_path
        if project_root is None:
            return
        rel_path = _relative_path(path, project_root)
        with self._lock:
            self._seen_files.discard(rel_path)
            self._symbol_cache.pop(rel_path, None)

        self._emit_file_deleted(rel_path)
        logger.debug("FILE_DELETED: %s", rel_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src_path = Path(event.src_path)
        dest_path = self._resolve(getattr(event, "dest_path", ""))
        project_root = self.collector.config.project_path
        if project_root is None:
            return

        if not _should_ignore(src_path):
            old_rel = _relative_path(src_path, project_root)
            with self._lock:
                self._seen_files.discard(old_rel)
                self._symbol_cache.pop(old_rel, None)
            self._emit_file_deleted(old_rel)

        if dest_path:
            new_rel = _relative_path(dest_path, project_root)
            with self._lock:
                self._seen_files.add(new_rel)
            self._emit_file_created(dest_path, new_rel)
            logger.debug("FILE_RENAMED/MOVED: %s -> %s", getattr(event, "src_path", ""), new_rel)


class ProjectFileWatcherCollector(BaseCollector):
    """
    Watches the configured project folder for file activity.

    Privacy: only the allowlisted project folder is observed.
    No file contents are read or transmitted — metadata only.
    """

    source_name = "VS_CODE"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._observer: Observer | None = None
        self._handler: _ProjectEventHandler | None = None
        self._session_started = False

    def _emit_session_started(self) -> None:
        if self._session_started:
            return
        self._session_started = True

        event = self.normalizer.normalize(
            source=EventSource.VS_CODE,
            event_type=EventType.PROJECT_SESSION_STARTED,
            title=f"Session started: {self.config.project_name}",
            description="Developer project monitoring session started",
            metadata={"project": self.config.project_name},
        )
        self.emit(event)

        event = self.normalizer.normalize(
            source=EventSource.VS_CODE,
            event_type=EventType.PROJECT_OPENED,
            title=f"Project opened: {self.config.project_name}",
            description=f"Monitoring project at {self.config.project_folder}",
            metadata={
                "project": self.config.project_name,
                "folder": self.config.project_folder,
            },
        )
        self.emit(event)

    def _emit_session_ended(self) -> None:
        if not self._session_started:
            return

        event = self.normalizer.normalize(
            source=EventSource.VS_CODE,
            event_type=EventType.PROJECT_SESSION_ENDED,
            title=f"Session ended: {self.config.project_name}",
            description="Developer project monitoring session ended",
            metadata={"project": self.config.project_name},
        )
        self.emit(event)
        self._session_started = False

    def start(self) -> None:
        if self._running:
            return

        project_path = self.config.project_path
        if project_path is None or not project_path.exists():
            logger.warning("Project folder not configured or does not exist — file watcher not started")
            return

        if "VS_CODE" not in self.config.allowed_sources:
            logger.info("VS_CODE source not in allowed_sources — skipping file watcher")
            return

        self._handler = _ProjectEventHandler(self)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(project_path), recursive=True)
        self._observer.start()
        self._running = True
        self._emit_session_started()
        logger.info("File watcher started on %s", project_path)

    def stop(self) -> None:
        if not self._running:
            return

        self._emit_session_ended()

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        self._handler = None
        self._running = False
        logger.info("File watcher stopped")
