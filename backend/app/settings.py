from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Everything the process reads from its environment; nothing else touches os.environ."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keitaro_base_url: str = "https://tlgk.host"
    keitaro_api_key: str
    campaign_name_prefix: str = "test_bulygin_"
    debug: bool = False
