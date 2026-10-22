import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Values that appear in docs, CI, or k8s placeholders and must never protect production.
_KNOWN_WEAK_SECRETS = {
    "test-jwt-secret-key-for-ci",
    "REPLACE_WITH_A_RANDOM_SECRET_OF_AT_LEAST_32_CHARACTERS",
    "changeme",
    "secret",
    "x",
}
MIN_PRODUCTION_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    DATABASE_URL: str = Field(..., min_length=1, repr=False, description="MySQL SQLAlchemy database URL")
    JWT_SECRET: str = Field(..., min_length=1, repr=False, description="JWT secret")
    WEB_ORIGIN: str = Field(..., min_length=1, description="Allowed web origin")
    # Telegram Emergency SOS (backend-only; never expose to mobile/web clients)
    TELEGRAM_BOT_TOKEN: str = Field(default="", repr=False, description="Telegram bot token (secret)")
    TELEGRAM_CHAT_ID: str = Field(default="", description="Telegram chat/group id for SOS alerts")

    # Deployment mode. When unset, Render deployments (RENDER env var) are treated as production.
    ENVIRONMENT: Literal["development", "test", "production"] | None = Field(default=None)
    # Refresh-cookie Secure flag. Defaults to True in production, False otherwise (local http).
    COOKIE_SECURE: bool | None = Field(default=None)
    # Interactive API docs (/docs, /redoc, /openapi.json). Defaults to off in production.
    ENABLE_API_DOCS: bool | None = Field(default=None)
    # Bearer token required for /metrics. In production /metrics is disabled unless this is set.
    METRICS_TOKEN: str = Field(default="", repr=False, description="Bearer token for /metrics (secret)")

    @field_validator("WEB_ORIGIN")
    @classmethod
    def _normalize_origin(cls, value: str) -> str:
        # Browsers send Origin without a trailing slash; CORS matching is exact.
        return value.strip().rstrip("/")

    @property
    def is_production(self) -> bool:
        if self.ENVIRONMENT is not None:
            return self.ENVIRONMENT == "production"
        return bool(os.environ.get("RENDER"))

    @property
    def cookie_secure(self) -> bool:
        return self.is_production if self.COOKIE_SECURE is None else self.COOKIE_SECURE

    @property
    def api_docs_enabled(self) -> bool:
        return (not self.is_production) if self.ENABLE_API_DOCS is None else self.ENABLE_API_DOCS

    @model_validator(mode="after")
    def _validate_production(self):
        if not self.is_production:
            return self

        problems = []
        if len(self.JWT_SECRET) < MIN_PRODUCTION_JWT_SECRET_LENGTH or self.JWT_SECRET in _KNOWN_WEAK_SECRETS:
            problems.append(f"JWT_SECRET must be a random value of at least {MIN_PRODUCTION_JWT_SECRET_LENGTH} characters")
        if not self.WEB_ORIGIN.startswith("https://") or "*" in self.WEB_ORIGIN:
            problems.append("WEB_ORIGIN must be a single https:// origin")
        if self.DATABASE_URL.startswith("sqlite"):
            problems.append("DATABASE_URL must not use SQLite in production")
        if self.COOKIE_SECURE is False:
            problems.append("COOKIE_SECURE must not be false in production")
        if bool(self.TELEGRAM_BOT_TOKEN.strip()) != bool(self.TELEGRAM_CHAT_ID.strip()):
            problems.append("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set together")
        if problems:
            # Messages name settings only; they never include secret values.
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
