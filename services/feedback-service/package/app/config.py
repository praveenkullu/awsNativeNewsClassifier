"""
Configuration for Feedback Service.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://mlnews:mlnews@localhost:5432/mlnews_feedback"
    )

    # Service
    service_name: str = "feedback-service"
    service_port: int = int(os.getenv("SERVICE_PORT", "8002"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"


settings = Settings()
