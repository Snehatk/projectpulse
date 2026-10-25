"""Integration Registry & Connection Manager for ProjectPulse AI."""

from typing import Any
from backend.integrations.asana.asana_adapter import AsanaAdapter
from backend.integrations.base.base_adapter import BasePMAdapter
from backend.integrations.clickup.clickup_adapter import ClickUpAdapter
from backend.integrations.jira.jira_adapter import JiraAdapter
from backend.integrations.linear.linear_adapter import LinearAdapter
from backend.integrations.monday.monday_adapter import MondayAdapter
from backend.integrations.trello.trello_adapter import TrelloAdapter


class IntegrationManager:
    """Manages adapter connections across Jira, monday, Asana, Trello, ClickUp, and Linear."""

    def __init__(self):
        self._adapters: dict[str, BasePMAdapter] = {
            "JIRA": JiraAdapter(),
        }
        # Only initialize Jira adapter if credentials or local config available
        self._adapters["JIRA"].connect({})

    def get_adapter(self, platform: str) -> BasePMAdapter | None:
        return self._adapters.get(platform.upper())

    def list_integrations(self) -> list[dict[str, Any]]:
        results = [
            {
                "platform": "JIRA",
                "connected": self._adapters["JIRA"].is_connected(),
                "status": "CONNECTED" if self._adapters["JIRA"].is_connected() else "NOT_CONNECTED",
                "supported_operations": ["get_projects", "get_tasks", "get_task", "connect", "disconnect", "sync"],
            }
        ]
        # Stub platforms explicitly marked NOT_IMPLEMENTED (no fake connected state)
        for name in ["MONDAY", "ASANA", "TRELLO", "CLICKUP", "LINEAR"]:
            results.append({
                "platform": name,
                "connected": False,
                "status": "NOT_IMPLEMENTED",
                "supported_operations": [],
            })
        return results

    def connect_platform(self, platform: str, credentials: dict[str, Any]) -> bool:
        adapter = self.get_adapter(platform)
        if not adapter:
            return False
        return adapter.connect(credentials)

    def disconnect_platform(self, platform: str) -> bool:
        adapter = self.get_adapter(platform)
        if not adapter:
            return False
        return adapter.disconnect()


integration_manager = IntegrationManager()
