"""
Configuration for API Gateway Service.
"""
import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service URLs
    inference_service_url: str = os.getenv("INFERENCE_SERVICE_URL", "http://inference-service:8001")
    feedback_service_url: str = os.getenv("FEEDBACK_SERVICE_URL", "http://feedback-service:8002")
    model_service_url: str = os.getenv("MODEL_SERVICE_URL", "http://model-service:8003")
    evaluation_service_url: str = os.getenv("EVALUATION_SERVICE_URL", "http://evaluation-service:8004")

    # Redis for rate limiting
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))

    # CORS
    allowed_origins: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    # Service
    service_name: str = "api-gateway"
    service_port: int = int(os.getenv("SERVICE_PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"


settings = Settings()
