from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PDF_", extra="ignore")

    service_token: str = ""
    max_file_bytes: int = 52_428_800
    parser_version: str = "1.0.0"
