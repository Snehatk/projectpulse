"""Source collectors — File watcher, Git activity, Build, Test, and QA collectors."""

import logging

from agent.backend_client import BackendClient
from agent.collectors.base import BaseCollector
from agent.collectors.build_collector import BuildCollector
from agent.collectors.file_watcher import ProjectFileWatcherCollector
from agent.collectors.git_watcher import GitActivityCollector
from agent.collectors.qa_collector import QACollector
from agent.collectors.report_watcher import ReportWatcherCollector
from agent.collectors.test_collector import TestCollector
from agent.config import AgentConfig
from agent.normalizer import EventNormalizer
from agent.privacy_filter import PrivacyFilter

logger = logging.getLogger(__name__)


class CollectorManager:
    """Manages File, Git, Build, Test, and QA collectors based on active role."""

    def __init__(self, config: AgentConfig, backend: BackendClient):
        self.config = config
        self.backend = backend
        self.normalizer = EventNormalizer(config)
        self.privacy_filter = PrivacyFilter(config)
        self._collectors: list[BaseCollector] = []
        self._events_sent = 0

    @property
    def events_sent(self) -> int:
        return self._events_sent

    def _on_event_sent(self, _event) -> None:
        self._events_sent += 1

    def _build_collectors(self) -> list[BaseCollector]:
        common = dict(
            config=self.config,
            normalizer=self.normalizer,
            privacy_filter=self.privacy_filter,
            backend=self.backend,
            on_event_sent=self._on_event_sent,
        )
        collectors: list[BaseCollector] = []

        sources = set(self.config.allowed_sources)
        role = getattr(self.config, "role", "DEVELOPER")

        # Developer Collectors
        if role == "DEVELOPER":
            if "VS_CODE" in sources or "FILE" in sources:
                collectors.append(ProjectFileWatcherCollector(**common))
            if "GIT" in sources:
                collectors.append(GitActivityCollector(**common))
            if "BUILD" in sources:
                collectors.append(BuildCollector(**common))

        # Tester Collectors
        if role in ("TESTER", "QA") or "TEST" in sources:
            collectors.append(TestCollector(**common))
            collectors.append(ReportWatcherCollector(**common))

        # QA Specific Collectors
        if role == "QA" or "QA" in sources:
            collectors.append(QACollector(**common))

        return collectors

    def get_collector(self, source_name: str) -> BaseCollector | None:
        for c in self._collectors:
            if c.source_name == source_name:
                return c
        return None

    def start(self) -> None:
        if self._collectors:
            return

        if not self.config.monitoring_active:
            logger.info("Monitoring paused — collectors not started")
            return

        self._collectors = self._build_collectors()
        for collector in self._collectors:
            try:
                collector.start()
                logger.info("Started collector: %s", collector.source_name)
            except Exception as exc:
                logger.error("Failed to start %s: %s", collector.source_name, exc)

    def stop(self) -> None:
        for collector in self._collectors:
            try:
                collector.stop()
            except Exception as exc:
                logger.error("Failed to stop %s: %s", collector.source_name, exc)
        self._collectors.clear()

    def restart(self) -> None:
        """Restart collectors (e.g. after config change or resume monitoring)."""
        self.stop()
        self.start()
