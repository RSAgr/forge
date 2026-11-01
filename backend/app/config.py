from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://civiclens:civiclens@localhost:5433/civiclens"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    aws_s3_bucket: str = ""
    jwt_secret_key: str = "replace-this-with-a-long-random-secret"
    admin_email: str = ""
    admin_password: str = ""
    storage_dir: str = "uploads"
    max_upload_bytes: int = 10_000_000
    app_base_url: str = "http://localhost:5173"
    nominatim_contact_email: str = ""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
