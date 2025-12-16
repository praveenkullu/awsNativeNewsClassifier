"""
Configuration for Evaluation Service.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://mlnews:mlnews@localhost:5432/mlnews_evaluation"
    )

    # Service URLs
    model_service_url: str = os.getenv("MODEL_SERVICE_URL", "http://model-service:8003")
    feedback_service_url: str = os.getenv("FEEDBACK_SERVICE_URL", "http://feedback-service:8002")

    # Thresholds
    performance_threshold: float = float(os.getenv("PERFORMANCE_THRESHOLD", "0.75"))
    correction_threshold: int = int(os.getenv("CORRECTION_THRESHOLD", "100"))

    # Service
    service_name: str = "evaluation-service"
    service_port: int = int(os.getenv("SERVICE_PORT", "8004"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"


settings = Settings()
