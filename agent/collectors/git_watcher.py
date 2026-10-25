"""Git activity collector — monitors only the configured project repository."""

import logging
import os
from pathlib import Path
import re
import subprocess
import threading
import time

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from agent.ast_analyzer import generate_deterministic_explanation
from agent.collectors.base import BaseCollector
from agent.collectors.git_parser import (
    GitSignal,
    GitSignalType,
    branch_from_ref_path,
    parse_push_log_line,
    parse_reflog_line,
    read_current_branch,
)
from shared.events import EventSource, EventType

logger = logging.getLogger(__name__)

SIGNAL_TO_EVENT = {
    GitSignalType.COMMIT: EventType.GIT_COMMIT,
    GitSignalType.BRANCH_CHANGED: EventType.GIT_BRANCH_CHANGED,
    GitSignalType.BRANCH_CREATED: EventType.GIT_BRANCH_CREATED,
    GitSignalType.PULL: EventType.GIT_PULL,
    GitSignalType.PUSH: EventType.GIT_PUSH,
}

PRE_PUSH_HOOK = """#!/bin/sh
# ProjectPulse AI — optional push detection hook (project-local only)
LOG_FILE=\"$(git rev-parse --git-dir)/projectpulse/push.log\"
mkdir -p \"$(dirname \"$LOG_FILE\")\"
while read local_ref local_sha remote_ref remote_sha; do
  branch=\"${local_ref#refs/heads/}\"
  echo \"PUSH|$branch|$local_sha|origin\" >> \"$LOG_FILE\"
done
exit 0
"""


class _GitOffsetTracker:
    """Tracks read offsets for git log files to process only new lines."""

    def __init__(self):
        self._offsets: dict[str, int] = {}
        self._known_branches: set[str] = set()
        self._lock = threading.Lock()

    def read_new_lines(self, path: Path, *, skip_existing: bool = True) -> list[str]:
        key = str(path)
        with self._lock:
            if not path.exists():
                return []

            size = path.stat().st_size
            if key not in self._offsets:
                self._offsets[key] = size if skip_existing else 0

            offset = self._offsets[key]
            if offset > size:
                offset = 0

            with path.open("r", encoding="utf-8", errors="ignore") as f:
                f.seek(offset)
                content = f.read()
                self._offsets[key] = f.tell()

        return [ln for ln in content.splitlines() if ln.strip()]

    def seed_existing_branches(self, heads_dir: Path) -> None:
        if not heads_dir.exists():
            return
        with self._lock:
            for ref in heads_dir.rglob("*"):
                if ref.is_file():
                    self._known_branches.add(branch_from_ref_path(ref))

    def check_new_branch(self, path: Path) -> str | None:
        if not path.is_file():
            return None
        if path.name.endswith(".lock"):
            return None
        branch = branch_from_ref_path(path)
        with self._lock:
            if branch in self._known_branches:
                return None
            self._known_branches.add(branch)
            return branch


class _GitEventHandler(FileSystemEventHandler):
    DEBOUNCE_SECONDS = 1.0

    def __init__(self, collector: "GitActivityCollector"):
        self.collector = collector
        self._last_handled: dict[str, float] = {}
        self._lock = threading.Lock()

    def _debounced(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last_handled.get(key, 0)
            if now - last < self.DEBOUNCE_SECONDS:
                return True
            self._last_handled[key] = now
            return False

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if self._debounced(str(path)):
            return
        self.collector.process_git_path(path)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        self.collector.process_git_path(path, created=True)


class GitActivityCollector(BaseCollector):
    """
    Monitors Git activity inside the configured project repo only.

    Watches .git/logs and refs within the project folder.
    Does not access other repositories or global git config.
    """

    source_name = "GIT"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._observer: Observer | None = None
        self._handler: _GitEventHandler | None = None
        self._tracker = _GitOffsetTracker()
        self._git_dir: Path | None = None
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()

    def _resolve_git_dir(self) -> Path | None:
        project = self.config.project_path
        if project is None:
            return None

        git_dir = project / ".git"
        if git_dir.is_dir():
            return git_dir

        # submodule or linked worktree: read gitdir pointer
        if git_dir.is_file():
            content = git_dir.read_text(encoding="utf-8", errors="ignore").strip()
            if content.startswith("gitdir:"):
                linked = Path(content.removeprefix("gitdir:").strip())
                if not linked.is_absolute():
                    linked = (project / linked).resolve()
                return linked if linked.exists() else None

        return None

    def _ensure_push_hook(self, git_dir: Path) -> None:
        """Install optional project-local pre-push hook for push detection."""
        hooks_dir = git_dir / "hooks"
        hook_path = hooks_dir / "pre-push"
        marker = git_dir / "projectpulse" / "hook_installed"

        if marker.exists():
            return

        if not hooks_dir.exists():
            return

        try:
            pulse_dir = git_dir / "projectpulse"
            pulse_dir.mkdir(exist_ok=True)

            if hook_path.exists():
                existing = hook_path.read_text(encoding="utf-8", errors="ignore")
                if "ProjectPulse AI" in existing:
                    marker.write_text("ok", encoding="utf-8")
                    return
                # Preserve existing hook — chain instead of overwrite
                wrapped = (
                    "#!/bin/sh\n"
                    "# ProjectPulse AI — chained pre-push hook\n"
                    f'LOG_FILE="$(git rev-parse --git-dir)/projectpulse/push.log"\n'
                    'mkdir -p "$(dirname "$LOG_FILE")"\n'
                    'branch="${1#refs/heads/}"\n'
                    'commit="$(git rev-parse HEAD 2>/dev/null || echo unknown)"\n'
                    'echo "PUSH|$branch|$commit|origin" >> "$LOG_FILE"\n'
                    f'exec "{hook_path}.original" "$@"\n'
                )
                if not (hooks_dir / "pre-push.original").exists():
                    hook_path.rename(hooks_dir / "pre-push.original")
                hook_path.write_text(wrapped, encoding="utf-8")
            else:
                hook_path.write_text(PRE_PUSH_HOOK, encoding="utf-8")

            if os.name != "nt":
                hook_path.chmod(hook_path.stat().st_mode | 0o111)

            marker.write_text("ok", encoding="utf-8")
            logger.info("Installed project-local pre-push hook for push detection")
        except OSError as exc:
            logger.warning("Could not install pre-push hook: %s", exc)

    def _emit_signal(self, signal: GitSignal, detected_on_catchup: bool = False) -> None:
        event_type = SIGNAL_TO_EVENT.get(signal.signal_type)
        if not event_type:
            return

        branch = signal.branch or read_current_branch(self._git_dir) if self._git_dir else "unknown"

        titles = {
            EventType.GIT_COMMIT: f"Commit on {branch}",
            EventType.GIT_BRANCH_CHANGED: f"Switched to branch {branch}",
            EventType.GIT_BRANCH_CREATED: f"Created branch {branch}",
            EventType.GIT_PULL: f"Pulled changes on {branch}",
            EventType.GIT_PUSH: f"Pushed branch {branch}",
        }

        task_key = None
        explanation = None
        files_changed = []

        if event_type == EventType.GIT_COMMIT and signal.commit_hash:
            match = re.search(r"\b([A-Z]{2,10}-\d+)\b", signal.message or "")
            if match:
                task_key = match.group(1)

            if self._git_dir:
                try:
                    out = subprocess.check_output(
                        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", signal.commit_hash],
                        cwd=str(self._git_dir.parent),
                        text=True,
                        stderr=subprocess.DEVNULL,
                    )
                    files_changed = [ln.strip() for ln in out.splitlines() if ln.strip()]
                except Exception:
                    pass

            explanation = generate_deterministic_explanation(
                files_changed=files_changed,
                commit_message=signal.message or "",
                task_key=task_key or "",
                detected_on_catchup=detected_on_catchup,
            )

            try:
                marker_file = self._git_dir / "projectpulse" / "last_seen_commit.txt"
                marker_file.parent.mkdir(parents=True, exist_ok=True)
                marker_file.write_text(signal.commit_hash, encoding="utf-8")
            except Exception:
                pass

        metadata = {
            "branch": branch,
            "commit_hash": signal.commit_hash,
            "commit_message": signal.message,
            "project": self.config.project_name,
            "detected_on_catchup": detected_on_catchup,
        }
        if task_key:
            metadata["task_key"] = task_key
        if files_changed:
            metadata["files_changed"] = files_changed
        if explanation:
            metadata["explanation"] = explanation

        title = titles.get(event_type, signal.signal_type.value)
        if detected_on_catchup and event_type == EventType.GIT_COMMIT:
            title = f"[Catch-up] {title}"

        event = self.normalizer.normalize(
            source=EventSource.GIT,
            event_type=event_type,
            title=title,
            description=signal.message or signal.raw_line,
            metadata=metadata,
        )
        self.emit(event)
        logger.info("Git event: %s (%s) [catchup=%s]", event_type.value, branch, detected_on_catchup)

    def process_git_path(self, path: Path, created: bool = False) -> None:
        if self._git_dir is None:
            return
        if not self.privacy_filter.allow_path(path):
            return

        rel = str(path).replace("\\", "/")

        # New branch ref file
        if "/refs/heads/" in rel and created:
            if path.name.endswith(".lock"):
                return
            branch = self._tracker.check_new_branch(path)
            if branch:
                self._emit_signal(
                    GitSignal(
                        signal_type=GitSignalType.BRANCH_CREATED,
                        branch=branch,
                        message=f"Branch created: {branch}",
                    )
                )
            return

        # Push log from pre-push hook
        if path.name == "push.log" and "projectpulse" in rel:
            for line in self._tracker.read_new_lines(path, skip_existing=not created):
                signal = parse_push_log_line(line)
                if signal:
                    self._emit_signal(signal)
            return

        # FETCH_HEAD update → pull
        if path.name == "FETCH_HEAD":
            for line in self._tracker.read_new_lines(path, skip_existing=not created):
                if line.strip():
                    branch = read_current_branch(self._git_dir)
                    self._emit_signal(
                        GitSignal(
                            signal_type=GitSignalType.PULL,
                            branch=branch,
                            message="Fetched/pulled remote changes",
                        )
                    )
            return

        # Reflog files
        if "/logs/" in rel:
            default_branch = read_current_branch(self._git_dir)
            if "/refs/heads/" in rel:
                default_branch = branch_from_ref_path(path)

            for line in self._tracker.read_new_lines(path):
                signal = parse_reflog_line(line, default_branch=default_branch)
                if signal:
                    self._emit_signal(signal)

    def _poll_git_logs(self) -> None:
        """Backup poll — Windows may miss .git filesystem events."""
        if self._git_dir is None:
            return

        logs_head = self._git_dir / "logs" / "HEAD"
        if logs_head.exists():
            self.process_git_path(logs_head)

        logs_heads = self._git_dir / "logs" / "refs" / "heads"
        if logs_heads.exists():
            for log_file in logs_heads.rglob("*"):
                if log_file.is_file():
                    self.process_git_path(log_file)

    def _poll_loop(self) -> None:
        while not self._poll_stop.wait(2.0):
            if self._running:
                try:
                    self._poll_git_logs()
                except Exception as exc:
                    logger.debug("Git poll error: %s", exc)

    def _init_git(self) -> bool:
        self._git_dir = self._resolve_git_dir()
        if self._git_dir is None:
            logger.warning("No .git directory in project — Git collector not started")
            return False

        if not self.privacy_filter.allow_path(self._git_dir):
            logger.warning("Git directory outside allowlist — Git collector blocked")
            return False

        heads_dir = self._git_dir / "refs" / "heads"
        self._tracker.seed_existing_branches(heads_dir)
        self._seed_log_offsets()
        self._catch_up_commits()
        self._ensure_push_hook(self._git_dir)
        return True

    def _catch_up_commits(self) -> None:
        """Startup catch-up: detect any commits created while agent was stopped and emit catchup events."""
        if self._git_dir is None:
            return
        pulse_dir = self._git_dir / "projectpulse"
        pulse_dir.mkdir(parents=True, exist_ok=True)
        marker_file = pulse_dir / "last_seen_commit.txt"

        repo_root = self._git_dir.parent
        try:
            head_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_root),
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return

        if not marker_file.exists():
            marker_file.write_text(head_sha, encoding="utf-8")
            return

        last_sha = marker_file.read_text(encoding="utf-8").strip()
        if last_sha and last_sha != head_sha:
            try:
                raw = subprocess.check_output(
                    ["git", "log", f"{last_sha}..HEAD", "--format=%H|||%s"],
                    cwd=str(repo_root),
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                branch = read_current_branch(self._git_dir)
                for line in reversed(raw.splitlines()):
                    if "|||" in line:
                        sha, msg = line.split("|||", 1)
                        self._emit_signal(
                            GitSignal(
                                signal_type=GitSignalType.COMMIT,
                                branch=branch,
                                commit_hash=sha.strip(),
                                message=msg.strip(),
                            ),
                            detected_on_catchup=True,
                        )
                logger.info("Startup Catch-up: Reconciled offline git commits from %s to %s", last_sha[:7], head_sha[:7])
            except Exception as exc:
                logger.debug("Failed catch-up git reconciliation: %s", exc)

        marker_file.write_text(head_sha, encoding="utf-8")

    def _seed_log_offsets(self) -> None:
        """Skip git history that existed before monitoring started."""
        if self._git_dir is None:
            return

        seed_paths: list[Path] = [self._git_dir / "logs" / "HEAD"]
        logs_heads = self._git_dir / "logs" / "refs" / "heads"
        if logs_heads.exists():
            seed_paths.extend(p for p in logs_heads.rglob("*") if p.is_file())

        for path in seed_paths:
            self._tracker.read_new_lines(path, skip_existing=True)

    def start(self) -> None:
        if self._running:
            return

        if "GIT" not in self.config.allowed_sources:
            logger.info("GIT source not in allowed_sources — skipping Git collector")
            return

        if not self._init_git():
            return

        logs_dir = self._git_dir / "logs"
        refs_dir = self._git_dir / "refs" / "heads"
        pulse_dir = self._git_dir / "projectpulse"

        watch_paths = [p for p in [logs_dir, refs_dir, pulse_dir, self._git_dir / "FETCH_HEAD"] if p.exists()]
        if not watch_paths:
            logger.warning("No Git watch paths found")
            return

        self._handler = _GitEventHandler(self)
        # PollingObserver is more reliable for .git on Windows
        self._observer = PollingObserver(timeout=1)

        for watch_path in watch_paths:
            if watch_path.is_file():
                watch_path = watch_path.parent
            self._observer.schedule(self._handler, str(watch_path), recursive=True)

        self._observer.start()
        self._running = True

        self._poll_stop.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        logger.info("Git collector started on %s", self._git_dir)

    def stop(self) -> None:
        if not self._running:
            return

        self._poll_stop.set()
        if self._poll_thread:
            self._poll_thread.join(timeout=3)
            self._poll_thread = None

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        self._handler = None
        self._running = False
        logger.info("Git collector stopped")

    @staticmethod
    def is_git_available() -> bool:
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                timeout=3,
                check=True,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
