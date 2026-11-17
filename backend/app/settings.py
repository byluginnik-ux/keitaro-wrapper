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
    db_pool_size: int = 5
    db_max_overflow: int = 10
    mongo_max_pool_size: int = 100

    message_bus: Literal["memory", "rabbitmq"] = "memory"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    task_max_attempts: int = 3
    task_retry_delay: float = 5.0
    outbox_poll: float = 0.5
    rabbitmq_prefetch: int = 10

    cache_backend: Literal["memory", "redis"] = "memory"
    redis_url: str = "redis://redis:6379/0"
    catalog_ttl: float = 30.0
