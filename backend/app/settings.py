from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Everything the process reads from its environment; nothing else touches os.environ."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keitaro_base_url: str = "https://tlgk.host"
    keitaro_api_key: SecretStr
    campaign_name_prefix: str = "test_bulygin_"
    debug: bool = False

    storage_backend: Literal["postgres", "mongo", "memory"] = "postgres"
    database_url: str = "postgresql+asyncpg://keitaro:keitaro@db:5432/keitaro"
    mongo_url: str = "mongodb://mongo:27017/?directConnection=true"
    mongo_database: str = "keitaro"
