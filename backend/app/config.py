from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(..., min_length=1, description="MySQL SQLAlchemy database URL")
    JWT_SECRET: str = Field(..., min_length=1, description="JWT secret")
    WEB_ORIGIN: str = Field(..., min_length=1, description="Allowed web origin")
    # Telegram Emergency SOS (backend-only; never expose to mobile/web clients)
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram bot token (secret)")
    TELEGRAM_CHAT_ID: str = Field(default="", description="Telegram chat/group id for SOS alerts")


@lru_cache
def get_settings() -> Settings:
    return Settings()
