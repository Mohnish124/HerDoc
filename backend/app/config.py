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


@lru_cache
def get_settings() -> Settings:
    return Settings()
