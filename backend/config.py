"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ProjectPulse AI"
    database_url: str = "sqlite:///./data/projectpulse.db"
    api_prefix: str = "/api"

    # Real Jira Cloud Configuration
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "KAN"

    # Authentication & Security
    secret_key: str = "projectpulse-super-secret-key-change-in-prod"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # Demo Mode Flag (False = clean start, True = explicit opt-in demo)
    demo_mode: bool = False

    # AI Service Configuration (Optional LLM keys)
    gemini_api_key: str = ""
    openai_api_key: str = ""
    ai_model_name: str = "gemini-1.5-flash"

    @property
    def data_dir(self) -> Path:
        url = self.database_url
        if url.startswith("sqlite:///"):
            db_path = Path(url.replace("sqlite:///", ""))
            return db_path.parent
        return Path("data")


settings = Settings()
