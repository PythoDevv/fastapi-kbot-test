from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: PostgresDsn
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    BASE_WEBHOOK_URL: str
    WEBHOOK_SECRET: str
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8001

    KITOBXON_BOT_TOKEN: str
    KITOBXON_ADMIN_IDS: list[int] = Field(default_factory=list)
    KITOBXON_WEBHOOK_PATH: str = "/kitobxon/webhook"

    LOG_LEVEL: str = "INFO"

    @property
    def database_url_str(self) -> str:
        return str(self.DATABASE_URL)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
