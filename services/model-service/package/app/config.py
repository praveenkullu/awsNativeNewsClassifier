"""
Configuration for Model Service.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://mlnews:mlnews@localhost:5432/mlnews_model"
    )

    # AWS
    aws_region: str = os.getenv("AWS_REGION", "us-east-2")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    s3_model_bucket: str = os.getenv("S3_MODEL_BUCKET", "ml-news-models-289140051471")
    s3_data_bucket: str = os.getenv("S3_DATA_BUCKET", "ml-news-data-289140051471")

    # SageMaker
    sagemaker_role_arn: str = os.getenv("SAGEMAKER_ROLE_ARN", "")

    # Training
    training_data_path: str = os.getenv(
        "TRAINING_DATA_PATH",
        "/app/data/News_Category_Dataset_v3.json"
    )
    models_dir: str = os.getenv("MODELS_DIR", "/app/models")

    # Service
    service_name: str = "model-service"
    service_port: int = int(os.getenv("SERVICE_PORT", "8003"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"


settings = Settings()
