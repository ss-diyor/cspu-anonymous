from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    bot_username: str | None = None
    database_url: str
    superadmin_ids: frozenset[int] = Field(default_factory=frozenset)
    channel_id: int
    moderation_chat_id: int
    discussion_chat_id: int

    webhook_base_url: str | None = None
    railway_public_domain: str | None = None
    webhook_path: str = "/telegram/webhook"
    webhook_secret: str

    app_mode: str = "webhook"
    log_level: str = "INFO"
    rate_limit_seconds: int = 20
    session_ttl_minutes: int = 30

    @field_validator("superadmin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> frozenset[int]:
        if value is None or value == "":
            return frozenset()
        if isinstance(value, int):
            return frozenset({value})
        if isinstance(value, str):
            return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
        return frozenset(value)  # type: ignore[arg-type]

    @field_validator("webhook_path")
    @classmethod
    def normalize_webhook_path(cls, value: str) -> str:
        return value if value.startswith("/") else f"/{value}"

    @field_validator("webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, value: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        if not 1 <= len(value) <= 256 or any(char not in allowed for char in value):
            raise ValueError("WEBHOOK_SECRET may contain only A-Z, a-z, 0-9, _ and -")
        return value

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def public_base_url(self) -> str | None:
        if self.webhook_base_url:
            return self.webhook_base_url.rstrip("/")
        if self.railway_public_domain:
            return f"https://{self.railway_public_domain.strip('/')}"
        return None

    @property
    def webhook_url(self) -> str | None:
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}{self.webhook_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
