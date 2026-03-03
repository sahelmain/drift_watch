from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SQLITE_URL = f"sqlite+aiosqlite:///{_BACKEND_ROOT / 'driftwatch.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    DATABASE_URL: str = _DEFAULT_SQLITE_URL
    REDIS_URL: str = "redis://localhost:6379/0"
    AUTO_CREATE_SCHEMA: bool = True
    ENABLE_INLINE_SCHEDULER: bool = True

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@driftwatch.io"

    SLACK_WEBHOOK_URL: str = ""

    PAGERDUTY_API_KEY: str = ""
    PAGERDUTY_SERVICE_ID: str = ""

    JIRA_URL: str = ""
    JIRA_USER: str = ""
    JIRA_TOKEN: str = ""
    JIRA_PROJECT: str = ""

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    OTEL_EXPORTER_ENDPOINT: str = "http://localhost:4317"

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://driftwatch.vercel.app",
    ]


settings = Settings()
