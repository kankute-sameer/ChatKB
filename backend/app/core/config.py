import json
from functools import lru_cache
from typing import cast

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    auth_users: dict[str, str]
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "postgresql+asyncpg://chatkb:chatkb@127.0.0.1:5433/chatkb"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-5.6-luna"
    llm_title_model: str = "gpt-4.1-mini"
    llm_reasoning_effort: str = "medium"
    llm_reasoning_summary: str = "auto"
    stream_buffer_ttl_seconds: int = 300
    exa_api_key: str
    log_level: str = "DEBUG"

    @field_validator("auth_users", mode="before")
    @classmethod
    def parse_auth_users(cls, value: object) -> object:
        if isinstance(value, str):
            parsed: object = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("AUTH_USERS must be a JSON object")
            return cast(dict[str, object], parsed)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
