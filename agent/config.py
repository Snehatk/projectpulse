"""Agent configuration — role-aware, multi-profile support."""

import json
import platform
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "agent_config.json"


@dataclass
class AgentConfig:
    agent_id: str = "AGENT-DEV-001"
    user_id: str = "DEV-001"
    user_name: str = "Alex Rivera"
    project_id: str = "PP"
    project_name: str = "Showcase Order Service"
    role: str = "DEVELOPER"  # DEVELOPER, TESTER, QA, PROJECT_MANAGER
    machine_name: str = field(default_factory=platform.node)
    machine_id: str = "LOCAL-MACHINE"
    project_folder: str = ""
    backend_url: str = "http://127.0.0.1:8000"
    frontend_url: str = "http://127.0.0.1:5173"
    device_token: str = ""
    device_id: str = ""
    monitoring_active: bool = True
    allowed_sources: list[str] = field(
        default_factory=lambda: ["FILE", "GIT", "BUILD", "TEST", "QA", "VS_CODE"]
    )
    autostart_with_windows: bool = False
    idle_threshold_seconds: float = 300.0
    vscode_auto_detect: bool = True
    custom_exclusions: list[str] = field(default_factory=list)
    config_file_path: Path = field(default=DEFAULT_CONFIG_PATH)

    @property
    def project_path(self) -> Path | None:
        if not self.project_folder:
            return None
        return Path(self.project_folder).resolve()

    def is_path_allowed(self, path: Path) -> bool:
        """Privacy filter: only paths inside the configured project folder."""
        if not self.monitoring_active:
            return False
        project = self.project_path
        if project is None or not project.exists():
            return False
        try:
            resolved = path.resolve()
            resolved.relative_to(project)
            # Check custom exclusions
            if self.custom_exclusions:
                path_str = str(resolved).lower()
                for excl in self.custom_exclusions:
                    if excl.lower() in path_str:
                        return False
            return True
        except ValueError:
            return False

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "role": self.role,
            "machine_name": self.machine_name,
            "machine_id": self.machine_id,
            "project_folder": self.project_folder,
            "backend_url": self.backend_url,
            "frontend_url": self.frontend_url,
            "device_token": self.device_token,
            "device_id": self.device_id,
            "monitoring_active": self.monitoring_active,
            "allowed_sources": self.allowed_sources,
            "autostart_with_windows": self.autostart_with_windows,
            "idle_threshold_seconds": self.idle_threshold_seconds,
            "vscode_auto_detect": self.vscode_auto_detect,
            "custom_exclusions": self.custom_exclusions,
        }

    def save(self, target_path: Path | None = None) -> None:
        p = target_path or self.config_file_path or DEFAULT_CONFIG_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, custom_path: Path | None = None) -> "AgentConfig":
        p = custom_path or DEFAULT_CONFIG_PATH
        if not p.exists():
            cfg = cls(config_file_path=p)
            cfg.save(p)
            return cfg
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return cls(
                agent_id=data.get("agent_id", "AGENT-DEV-001"),
                user_id=data.get("user_id", "DEV-001"),
                user_name=data.get("user_name", "Alex Rivera"),
                project_id=data.get("project_id", "PP"),
                project_name=data.get("project_name", "Showcase Order Service"),
                role=data.get("role", "DEVELOPER"),
                machine_name=data.get("machine_name", platform.node()),
                machine_id=data.get("machine_id", "LOCAL-MACHINE"),
                project_folder=data.get("project_folder", ""),
                backend_url=data.get("backend_url", "http://127.0.0.1:8000"),
                frontend_url=data.get("frontend_url", "http://127.0.0.1:5173"),
                device_token=data.get("device_token", ""),
                device_id=data.get("device_id", ""),
                monitoring_active=data.get("monitoring_active", True),
                allowed_sources=data.get(
                    "allowed_sources", ["FILE", "GIT", "BUILD", "TEST", "QA", "VS_CODE"]
                ),
                autostart_with_windows=data.get("autostart_with_windows", False),
                idle_threshold_seconds=float(data.get("idle_threshold_seconds", 300.0)),
                vscode_auto_detect=data.get("vscode_auto_detect", True),
                custom_exclusions=data.get("custom_exclusions", []),
                config_file_path=p,
            )
        except Exception:
            cfg = cls(config_file_path=p)
            cfg.save(p)
            return cfg
