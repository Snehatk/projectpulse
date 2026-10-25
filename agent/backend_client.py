"""HTTP client for sending normalized events and heartbeat to the backend."""

import logging
import httpx

from agent.config import AgentConfig
from agent.event_queue import EventQueue
from shared.events import ProjectEventCreate

logger = logging.getLogger(__name__)


class BackendClient:
    def __init__(self, config: AgentConfig, event_queue: EventQueue | None = None):
        self.config = config
        self.base_url = config.backend_url.rstrip("/")
        self.event_queue = event_queue or EventQueue()
        self._registered = False

    @property
    def is_ready(self) -> bool:
        return bool(self.config.project_id and self.config.user_id)

    def health_check(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/health", timeout=3.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.device_token:
            headers["Authorization"] = f"Bearer {self.config.device_token}"
        return headers

    def _direct_send(self, payload: dict) -> bool:
        """Direct HTTP post to /api/events used by the persistent queue flusher."""
        try:
            response = httpx.post(
                f"{self.base_url}/api/events",
                json=payload,
                headers=self._get_headers(),
                timeout=5.0,
            )
            if response.status_code == 201:
                return True
            if response.status_code == 401:
                logger.error("Agent device token is invalid or revoked by the Project Manager!")
            else:
                logger.warning("Backend rejected event with code %d: %s", response.status_code, response.text)
            return False
        except Exception as exc:
            logger.debug("Direct send network failure: %s", exc)
            return False

    def send_event(self, event: ProjectEventCreate) -> bool:
        if not self.config.monitoring_active:
            return False

        # Ensure agent_id is populated from config
        if not event.agent_id or event.agent_id == "AGENT-DEFAULT":
            event.agent_id = self.config.agent_id

        # 1. First, always persist event to local SQLite queue
        self.event_queue.enqueue(event)

        # 2. Flush pending events to backend
        flushed = self.event_queue.flush(self._direct_send)
        return flushed > 0

    def get_developer_summary(self) -> dict | None:
        if not self.is_ready:
            return None
        try:
            response = httpx.get(
                f"{self.base_url}/api/projects/{self.config.project_id}/summary",
                params={"user_id": self.config.user_id},
                timeout=5.0,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning("Summary request failed: %s", response.text)
            return None
        except httpx.HTTPError as exc:
            logger.warning("Failed to load developer summary: %s", exc)
            return None

    def set_monitoring_status(self, active: bool) -> bool:
        try:
            response = httpx.post(
                f"{self.base_url}/api/monitoring-status",
                json={"active": active, "project_id": self.config.project_id or None},
                timeout=5.0,
            )
            return response.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("Failed to update monitoring status: %s", exc)
            return False

    def send_heartbeat(self) -> bool:
        try:
            response = httpx.post(
                f"{self.base_url}/api/agents/heartbeat",
                json={"agent_id": self.config.agent_id, "monitoring_active": self.config.monitoring_active},
                headers=self._get_headers(),
                timeout=4.0,
            )
            # Flush queue if heartbeat succeeded and there are pending items
            if response.status_code == 200 and self.event_queue.pending_count > 0:
                self.event_queue.flush(self._direct_send)
            return response.status_code == 200
        except Exception:
            return False

    def ensure_registered(self) -> bool:
        """Register user, project, and agent installation with backend."""
        if not self.health_check():
            return False

        try:
            if not self.config.user_id:
                response = httpx.post(
                    f"{self.base_url}/api/users",
                    json={"name": self.config.user_name, "role": self.config.role},
                    timeout=5.0,
                )
                response.raise_for_status()
                self.config.user_id = response.json()["user_id"]

            if not self.config.project_id and self.config.project_folder:
                response = httpx.post(
                    f"{self.base_url}/api/projects",
                    json={
                        "name": self.config.project_name,
                        "folder_path": self.config.project_folder,
                        "owner_user_id": self.config.user_id,
                    },
                    timeout=5.0,
                )
                response.raise_for_status()
                self.config.project_id = response.json()["project_id"]

            # Register Agent entity with backend
            httpx.post(
                f"{self.base_url}/api/agents/register",
                json={
                    "agent_id": self.config.agent_id,
                    "user_id": self.config.user_id,
                    "project_id": self.config.project_id,
                    "role": self.config.role,
                    "machine_name": self.config.machine_name,
                    "machine_id": self.config.machine_id,
                },
                timeout=5.0,
            )

            self.config.save()
            self._registered = True
            self.flush_queue()
            return True
        except httpx.HTTPError as exc:
            logger.warning("Backend registration failed: %s", exc)
            return False

    def flush_queue(self) -> int:
        if not self.is_ready:
            return 0
        return self.event_queue.flush(self._send_direct)

    def _send_direct(self, event: ProjectEventCreate) -> bool:
        try:
            if not event.agent_id or event.agent_id == "AGENT-DEFAULT":
                event.agent_id = self.config.agent_id
            payload = event.model_dump(mode="json")
            response = httpx.post(
                f"{self.base_url}/api/events",
                json=payload,
                timeout=5.0,
            )
            return response.status_code == 201
        except httpx.HTTPError:
            return False
