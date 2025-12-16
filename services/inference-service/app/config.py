"""
Configuration for Inference Service.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Redis
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))

    # AWS
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_model_bucket: str = os.getenv("S3_MODEL_BUCKET", "")

    # Model
    default_model_path: str = os.getenv("MODEL_PATH", "/app/models/default/model.pkl")
    model_service_url: str = os.getenv("MODEL_SERVICE_URL", "http://model-service:8003")

    # Cache
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

    # Service
    service_name: str = "inference-service"
    service_port: int = int(os.getenv("SERVICE_PORT", "8001"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"


settings = Settings()
