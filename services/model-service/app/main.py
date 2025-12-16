"""
Model Service - Handles model training, versioning, and storage.
"""
import os
import uuid
import pickle
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError

from .database import Database, ModelVersion, TrainingJob
from .config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

# Global state
db: Optional[Database] = None
training_jobs: Dict[str, Dict[str, Any]] = {}
s3_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db, s3_client

    logger.info("Starting Model Service")

    # Initialize database
    db = Database(settings.database_url)
    await db.initialize()

    # Initialize S3 client
    if settings.aws_region:
        s3_client = boto3.client('s3', region_name=settings.aws_region)

    yield

    # Cleanup
    if db:
        await db.close()
    logger.info("Model Service shutdown complete")


app = FastAPI(
    title="Model Service",
    description="Model training, versioning, and storage service",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class TrainingConfig(BaseModel):
    epochs: int = Field(default=10, ge=1, le=100)
    batch_size: int = Field(default=32, ge=8, le=256)
    learning_rate: float = Field(default=0.001, gt=0, lt=1)
    model_type: str = Field(default="logistic_regression")
    max_features: int = Field(default=10000, ge=1000, le=50000)


class TrainRequest(BaseModel):
    include_feedback: bool = Field(default=True)
    config: Optional[TrainingConfig] = None
    description: Optional[str] = None


class TrainResponse(BaseModel):
    training_job_id: str
    status: str
    estimated_duration_minutes: int
    message: str
    correlation_id: str


class TrainingJobStatus(BaseModel):
    training_job_id: str
    status: str
    progress: float
    current_epoch: Optional[int] = None
    total_epochs: Optional[int] = None
    metrics: Optional[Dict[str, float]] = None
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    error_message: Optional[str] = None
    correlation_id: str


class ModelVersionInfo(BaseModel):
    version: str
    status: str
    created_at: str
    metrics: Dict[str, float]
    training_job_id: Optional[str]
    is_production: bool


class ModelVersionsResponse(BaseModel):
    versions: List[ModelVersionInfo]
    total: int
    limit: int
    offset: int
    correlation_id: str


class DeployResponse(BaseModel):
    version: str
    status: str
    message: str
    previous_version: Optional[str]
    correlation_id: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str


# Helper functions
def get_correlation_id(x_correlation_id: Optional[str] = None) -> str:
    """Get or generate correlation ID."""
    return x_correlation_id or str(uuid.uuid4())


def run_training_job_sync(
    job_id: str,
    config: TrainingConfig,
    include_feedback: bool,
    description: Optional[str]
):
    """Start SageMaker training job synchronously (no background polling)."""
    training_jobs[job_id]['status'] = 'starting'
    training_jobs[job_id]['started_at'] = datetime.utcnow().isoformat()

    logger.info("Starting SageMaker training job", job_id=job_id)

    # Create SageMaker client
    sagemaker_client = boto3.client('sagemaker', region_name=settings.aws_region or 'us-east-2')

    # Generate model version
    model_version = f"v{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    training_job_name = f"ml-news-{job_id}"

    # SageMaker training job configuration
    training_params = {
        'TrainingJobName': training_job_name,
        'RoleArn': settings.sagemaker_role_arn or 'arn:aws:iam::289140051471:role/ml-news-sagemaker-role',
        'AlgorithmSpecification': {
            'TrainingImage': '257758044811.dkr.ecr.us-east-2.amazonaws.com/sagemaker-scikit-learn:1.0-1-cpu-py3',
            'TrainingInputMode': 'File'
        },
        'InputDataConfig': [
            {
                'ChannelName': 'training',
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri': f"s3://{settings.s3_data_bucket or 'ml-news-data-289140051471'}/data/",
                        'S3DataDistributionType': 'FullyReplicated'
                    }
                },
                'ContentType': 'application/json',
                'CompressionType': 'None'
            }
        ],
        'OutputDataConfig': {
            'S3OutputPath': f"s3://{settings.s3_model_bucket}/models/{model_version}/"
        },
        'ResourceConfig': {
            'InstanceType': 'ml.m5.large',
            'InstanceCount': 1,
            'VolumeSizeInGB': 10
        },
        'StoppingCondition': {
            'MaxRuntimeInSeconds': 3600,
            'MaxWaitTimeInSeconds': 7200  # 2x MaxRuntime for spot training
        },
        'HyperParameters': {
            'sagemaker_program': 'train.py',
            'sagemaker_submit_directory': f"s3://{settings.s3_data_bucket or 'ml-news-data-289140051471'}/code/sourcedir.tar.gz",
            'model_type': config.model_type,
            'max_features': str(config.max_features),
            'include_feedback': str(include_feedback).lower()
        },
        'EnableManagedSpotTraining': True,  # 70% cost savings
        'Tags': [
            {'Key': 'Project', 'Value': 'ml-news'},
            {'Key': 'JobId', 'Value': job_id}
        ]
    }

    # Start SageMaker training job
    response = sagemaker_client.create_training_job(**training_params)

    # Update job status with SageMaker job name
    training_jobs[job_id]['sagemaker_job_name'] = training_job_name
    training_jobs[job_id]['version'] = model_version
    training_jobs[job_id]['status'] = 'training'
    training_jobs[job_id]['message'] = 'SageMaker training job started'

    logger.info(
        "SageMaker training job started",
        job_id=job_id,
        sagemaker_job_name=training_job_name,
        version=model_version
    )

    # Note: Polling should be done via a separate endpoint or EventBridge/SNS
    # Lambda execution context will freeze after response, so no background polling


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="model-service",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.post("/api/v1/model/train", response_model=TrainResponse, status_code=202)
async def trigger_training(
    request: TrainRequest,
    x_correlation_id: Optional[str] = Header(None)
):
    """Trigger model training job."""
    correlation_id = get_correlation_id(x_correlation_id)

    logger.info(
        "Training request received",
        correlation_id=correlation_id,
        include_feedback=request.include_feedback
    )

    # Generate job ID (use hyphen for SageMaker compatibility)
    job_id = f"train-{uuid.uuid4().hex[:12]}"

    # Initialize job tracking
    config = request.config or TrainingConfig()
    training_jobs[job_id] = {
        'job_id': job_id,
        'status': 'queued',
        'config': config.model_dump(),
        'include_feedback': request.include_feedback,
        'description': request.description,
        'created_at': datetime.utcnow().isoformat(),
        'progress': 0.0
    }

    # Start training immediately (not in background - Lambda doesn't support background tasks)
    try:
        run_training_job_sync(job_id, config, request.include_feedback, request.description)
    except Exception as e:
        logger.error("Failed to start training", job_id=job_id, error=str(e))
        training_jobs[job_id]['status'] = 'failed'
        training_jobs[job_id]['error_message'] = str(e)

    return TrainResponse(
        training_job_id=job_id,
        status=training_jobs[job_id]['status'],
        estimated_duration_minutes=30,
        message="Training job started" if training_jobs[job_id]['status'] == 'training' else f"Training failed: {training_jobs[job_id].get('error_message', 'Unknown error')}",
        correlation_id=correlation_id
    )


@app.get("/api/v1/model/train/{job_id}", response_model=TrainingJobStatus)
async def get_training_status(
    job_id: str,
    x_correlation_id: Optional[str] = Header(None)
):
    """Get training job status."""
    correlation_id = get_correlation_id(x_correlation_id)

    if job_id not in training_jobs:
        raise HTTPException(status_code=404, detail="Training job not found")

    job = training_jobs[job_id]

    # Extract only numeric metrics to avoid Pydantic validation errors
    metrics = None
    if job.get('metrics'):
        metrics = {
            'accuracy': job.get('metrics', {}).get('accuracy', 0),
            'f1_score': job.get('metrics', {}).get('f1_score', 0),
            'precision': job.get('metrics', {}).get('precision', 0),
            'recall': job.get('metrics', {}).get('recall', 0)
        }

    return TrainingJobStatus(
        training_job_id=job_id,
        status=job['status'],
        progress=job.get('progress', 0.0),
        current_epoch=job.get('current_epoch'),
        total_epochs=job.get('config', {}).get('epochs'),
        metrics=metrics,
        started_at=job.get('started_at'),
        estimated_completion=job.get('estimated_completion'),
        error_message=job.get('error_message'),
        correlation_id=correlation_id
    )


@app.get("/api/v1/model/versions", response_model=ModelVersionsResponse)
async def list_model_versions(
    limit: int = 10,
    offset: int = 0,
    status: Optional[str] = None,
    x_correlation_id: Optional[str] = Header(None)
):
    """List all model versions."""
    correlation_id = get_correlation_id(x_correlation_id)

    versions = []

    # If database is available, use it
    if db:
        try:
            db_versions = await db.list_model_versions(limit=limit, offset=offset, status=status)
            total = len(db_versions)

            for v in db_versions:
                versions.append(ModelVersionInfo(
                    version=v.version,
                    status=v.status or 'active',
                    created_at=v.created_at.isoformat() if v.created_at else datetime.utcnow().isoformat(),
                    metrics=v.metrics or {},
                    training_job_id=v.training_job_id or '',
                    is_production=v.is_production or False
                ))

            return ModelVersionsResponse(
                versions=versions,
                total=total,
                limit=limit,
                offset=offset,
                correlation_id=correlation_id
            )
        except Exception as e:
            logger.warning("Failed to fetch from database, falling back to S3", error=str(e))

    # Fallback: read from S3 directly
    if s3_client:
        try:
            response = s3_client.list_objects_v2(
                Bucket=settings.s3_model_bucket,
                Prefix='models/',
                Delimiter='/'
            )

            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    version_name = prefix['Prefix'].rstrip('/').split('/')[-1]
                    if version_name and version_name != 'latest':
                        versions.append(ModelVersionInfo(
                            version=version_name,
                            status='active',
                            created_at=datetime.utcnow().isoformat(),
                            metrics={},
                            training_job_id='',
                            is_production=False
                        ))

            total = len(versions)
            versions = versions[offset:offset + limit]

            return ModelVersionsResponse(
                versions=versions,
                total=total,
                limit=limit,
                offset=offset,
                correlation_id=correlation_id
            )
        except Exception as e:
            logger.error("Failed to list S3 model versions", error=str(e))

    # Final fallback: return empty list
    return ModelVersionsResponse(
        versions=[],
        total=0,
        limit=limit,
        offset=offset,
        correlation_id=correlation_id
    )


@app.post("/api/v1/model/deploy/{version}", response_model=DeployResponse)
async def deploy_model(
    version: str,
    x_correlation_id: Optional[str] = Header(None)
):
    """Deploy a specific model version to production."""
    correlation_id = get_correlation_id(x_correlation_id)

    logger.info("Deploy request received", version=version, correlation_id=correlation_id)

    # Find the version
    target_job = None
    previous_version = None

    for job_id, job in training_jobs.items():
        if job.get('version') == version:
            target_job = job
        if job.get('is_production', False):
            previous_version = job.get('version')
            job['is_production'] = False

    if not target_job:
        raise HTTPException(status_code=404, detail=f"Model version {version} not found")

    target_job['is_production'] = True
    target_job['deploy_status'] = 'active'

    logger.info(
        "Model deployed",
        version=version,
        previous_version=previous_version,
        correlation_id=correlation_id
    )

    return DeployResponse(
        version=version,
        status="deployed",
        message="Model deployment successful",
        previous_version=previous_version,
        correlation_id=correlation_id
    )


@app.get("/api/v1/model/active")
async def get_active_model(x_correlation_id: Optional[str] = Header(None)):
    """Get the currently active model info."""
    correlation_id = get_correlation_id(x_correlation_id)

    for job_id, job in training_jobs.items():
        if job.get('is_production', False):
            return {
                'version': job['version'],
                'model_path': job.get('model_path'),
                's3_path': job.get('s3_path'),
                'metrics': job.get('metrics'),
                'correlation_id': correlation_id
            }

    # Return default model if no production model
    return {
        'version': 'default',
        'model_path': '/app/models/default/model.pkl',
        'message': 'No production model deployed',
        'correlation_id': correlation_id
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
