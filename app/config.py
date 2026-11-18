from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI Starter"
    app_version: str = "0.1.0"
    
    app_delta_base_url: str = ""
    app_delta_api_key: str = ""
    app_delta_api_secret: str = ""
    app_tbt_base_url: str = ""
    app_tbt_order_level_path: str = "/order-levels"
    app_tbt_api_key: str = ""
    app_tbt_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(env_file=".env.dev", env_file_encoding="utf-8")


settings = Settings()
