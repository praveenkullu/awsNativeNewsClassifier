"""
Evaluation Service - Evaluates models and triggers retraining when needed.
"""
import os
import uuid
import pickle
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from enum import Enum

import structlog
import numpy as np
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Integer, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import httpx

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

# Database setup
Base = declarative_base()


class EvaluationRecord(Base):
    """Evaluation database model."""

    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id = Column(String(100), unique=True, nullable=False, index=True)
    model_version = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")
    test_data_source = Column(String(50))
    metrics = Column(JSON)
    category_metrics = Column(JSON)
    comparison = Column(JSON)
    meets_threshold = Column(Boolean)
    recommendation = Column(String(100))
    error_message = Column(String(2000))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class RetrainingCheck(Base):
    """Retraining check history."""

    __tablename__ = "retraining_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    check_id = Column(String(100), unique=True, nullable=False)
    needs_retraining = Column(Boolean, default=False)
    reasons = Column(JSON)
    metrics = Column(JSON)
    recommendation = Column(String(100))
    training_triggered = Column(Boolean, default=False)
    training_job_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)


# Database manager
class Database:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.session_factory = sessionmaker(bind=self.engine)

    def initialize(self):
        Base.metadata.create_all(self.engine)

    def get_session(self):
        return self.session_factory()

    def close(self):
        self.engine.dispose()


# Global state
db: Optional[Database] = None
evaluation_jobs: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db

    logger.info("Starting Evaluation Service")

    # Initialize database
    db = Database(settings.database_url)
    db.initialize()

    yield

    # Cleanup
    if db:
        db.close()
    logger.info("Evaluation Service shutdown complete")


app = FastAPI(
    title="Evaluation Service",
    description="Model evaluation and retraining decision service",
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


# Enums
class TestDataSource(str, Enum):
    HOLDOUT = "holdout"
    FEEDBACK = "feedback"
    BOTH = "both"


# Request/Response Models
class EvaluateRequest(BaseModel):
    version: str = Field(..., min_length=1)
    test_data_source: TestDataSource = TestDataSource.HOLDOUT
    include_feedback_data: bool = True


class EvaluateResponse(BaseModel):
    evaluation_id: str
    version: str
    status: str
    message: str
    correlation_id: str


class MetricsResult(BaseModel):
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    confusion_matrix: Optional[str] = None


class CategoryMetrics(BaseModel):
    precision: float
    recall: float
    f1: float


class ComparisonResult(BaseModel):
    accuracy_diff: float
    f1_diff: float
    recommendation: str
    meets_threshold: bool


class EvaluationResult(BaseModel):
    evaluation_id: str
    version: str
    status: str
    metrics: Optional[MetricsResult] = None
    category_metrics: Optional[Dict[str, CategoryMetrics]] = None
    comparison_with_production: Optional[ComparisonResult] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    correlation_id: str


class RetrainCheckResponse(BaseModel):
    needs_retraining: bool
    reasons: List[str]
    current_metrics: Dict[str, float]
    recommendation: str
    last_check: str
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


async def run_evaluation(
    evaluation_id: str,
    version: str,
    test_data_source: TestDataSource,
    include_feedback: bool
):
    """Background task to run model evaluation."""
    try:
        evaluation_jobs[evaluation_id]['status'] = 'running'
        evaluation_jobs[evaluation_id]['started_at'] = datetime.utcnow().isoformat()

        logger.info("Starting evaluation", evaluation_id=evaluation_id, version=version)

        # Get model from model service
        async with httpx.AsyncClient() as client:
            # Get model info
            model_response = await client.get(
                f"{settings.model_service_url}/api/v1/model/active",
                timeout=30.0
            )

            if model_response.status_code != 200:
                raise Exception("Failed to get model info")

            model_info = model_response.json()
            production_version = model_info.get('version')
            production_metrics = model_info.get('metrics', {})

        # Simulate evaluation (in production, would load actual test data)
        # For demo, generate mock metrics
        import random
        base_accuracy = 0.82 + random.uniform(-0.05, 0.05)

        metrics = {
            'accuracy': round(base_accuracy, 4),
            'precision': round(base_accuracy - 0.02 + random.uniform(-0.02, 0.02), 4),
            'recall': round(base_accuracy - 0.03 + random.uniform(-0.02, 0.02), 4),
            'f1_score': round(base_accuracy - 0.025 + random.uniform(-0.02, 0.02), 4)
        }

        # Category-level metrics (sample)
        category_metrics = {
            'POLITICS': {'precision': 0.89, 'recall': 0.87, 'f1': 0.88},
            'BUSINESS': {'precision': 0.85, 'recall': 0.83, 'f1': 0.84},
            'ENTERTAINMENT': {'precision': 0.88, 'recall': 0.86, 'f1': 0.87},
            'SPORTS': {'precision': 0.91, 'recall': 0.90, 'f1': 0.905}
        }

        # Compare with production
        prod_accuracy = production_metrics.get('accuracy', 0.80)
        prod_f1 = production_metrics.get('f1_score', 0.78)

        accuracy_diff = metrics['accuracy'] - prod_accuracy
        f1_diff = metrics['f1_score'] - prod_f1
        meets_threshold = metrics['accuracy'] >= settings.performance_threshold

        if accuracy_diff > 0.01 and meets_threshold:
            recommendation = 'deploy'
        elif accuracy_diff > -0.01:
            recommendation = 'keep_current'
        else:
            recommendation = 'investigate'

        comparison = {
            'accuracy_diff': round(accuracy_diff, 4),
            'f1_diff': round(f1_diff, 4),
            'recommendation': recommendation,
            'meets_threshold': meets_threshold
        }

        # Update job status
        evaluation_jobs[evaluation_id].update({
            'status': 'completed',
            'metrics': metrics,
            'category_metrics': category_metrics,
            'comparison': comparison,
            'meets_threshold': meets_threshold,
            'recommendation': recommendation,
            'completed_at': datetime.utcnow().isoformat()
        })

        # Store in database
        with db.get_session() as session:
            record = EvaluationRecord(
                evaluation_id=evaluation_id,
                model_version=version,
                status='completed',
                test_data_source=test_data_source.value,
                metrics=metrics,
                category_metrics=category_metrics,
                comparison=comparison,
                meets_threshold=meets_threshold,
                recommendation=recommendation,
                completed_at=datetime.utcnow()
            )
            session.add(record)
            session.commit()

        logger.info(
            "Evaluation completed",
            evaluation_id=evaluation_id,
            accuracy=metrics['accuracy'],
            recommendation=recommendation
        )

    except Exception as e:
        evaluation_jobs[evaluation_id]['status'] = 'failed'
        evaluation_jobs[evaluation_id]['error_message'] = str(e)
        logger.error("Evaluation failed", evaluation_id=evaluation_id, error=str(e))


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="evaluation-service",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.post("/api/v1/model/evaluate", response_model=EvaluateResponse, status_code=202)
async def evaluate_model(
    request: EvaluateRequest,
    background_tasks: BackgroundTasks,
    x_correlation_id: Optional[str] = Header(None)
):
    """Evaluate a model version."""
    correlation_id = get_correlation_id(x_correlation_id)
    evaluation_id = f"eval_{uuid.uuid4().hex[:12]}"

    logger.info(
        "Evaluation request received",
        correlation_id=correlation_id,
        version=request.version
    )

    # Initialize evaluation tracking
    evaluation_jobs[evaluation_id] = {
        'evaluation_id': evaluation_id,
        'version': request.version,
        'status': 'pending',
        'test_data_source': request.test_data_source.value,
        'created_at': datetime.utcnow().isoformat()
    }

    # Start evaluation in background
    background_tasks.add_task(
        run_evaluation,
        evaluation_id,
        request.version,
        request.test_data_source,
        request.include_feedback_data
    )

    return EvaluateResponse(
        evaluation_id=evaluation_id,
        version=request.version,
        status="running",
        message="Evaluation started",
        correlation_id=correlation_id
    )


@app.get("/api/v1/model/evaluate/{evaluation_id}", response_model=EvaluationResult)
async def get_evaluation_result(
    evaluation_id: str,
    x_correlation_id: Optional[str] = Header(None)
):
    """Get evaluation results."""
    correlation_id = get_correlation_id(x_correlation_id)

    if evaluation_id not in evaluation_jobs:
        # Try database
        with db.get_session() as session:
            record = session.query(EvaluationRecord).filter(
                EvaluationRecord.evaluation_id == evaluation_id
            ).first()

            if not record:
                raise HTTPException(status_code=404, detail="Evaluation not found")

            return EvaluationResult(
                evaluation_id=record.evaluation_id,
                version=record.model_version,
                status=record.status,
                metrics=MetricsResult(**record.metrics) if record.metrics else None,
                category_metrics={
                    k: CategoryMetrics(**v) for k, v in record.category_metrics.items()
                } if record.category_metrics else None,
                comparison_with_production=ComparisonResult(**record.comparison) if record.comparison else None,
                completed_at=record.completed_at.isoformat() if record.completed_at else None,
                error_message=record.error_message,
                correlation_id=correlation_id
            )

    job = evaluation_jobs[evaluation_id]

    return EvaluationResult(
        evaluation_id=evaluation_id,
        version=job['version'],
        status=job['status'],
        metrics=MetricsResult(**job['metrics']) if job.get('metrics') else None,
        category_metrics={
            k: CategoryMetrics(**v) for k, v in job['category_metrics'].items()
        } if job.get('category_metrics') else None,
        comparison_with_production=ComparisonResult(**job['comparison']) if job.get('comparison') else None,
        completed_at=job.get('completed_at'),
        error_message=job.get('error_message'),
        correlation_id=correlation_id
    )


@app.post("/api/v1/model/retrain-check", response_model=RetrainCheckResponse)
async def check_retraining_needed(
    x_correlation_id: Optional[str] = Header(None)
):
    """Check if model retraining is needed based on feedback and performance."""
    correlation_id = get_correlation_id(x_correlation_id)
    check_id = f"check_{uuid.uuid4().hex[:12]}"

    logger.info("Retrain check requested", correlation_id=correlation_id)

    reasons = []
    needs_retraining = False

    try:
        # Get feedback stats from feedback service
        async with httpx.AsyncClient() as client:
            # Get feedback statistics
            feedback_response = await client.get(
                f"{settings.feedback_service_url}/api/v1/feedback/stats",
                timeout=30.0
            )

            feedback_stats = {}
            if feedback_response.status_code == 200:
                feedback_stats = feedback_response.json()

            # Get current model metrics
            model_response = await client.get(
                f"{settings.model_service_url}/api/v1/model/active",
                timeout=30.0
            )

            model_info = {}
            if model_response.status_code == 200:
                model_info = model_response.json()

        # Analyze metrics
        feedback_accuracy = feedback_stats.get('accuracy_from_feedback', 1.0)
        total_feedback = feedback_stats.get('total_feedback', 0)
        corrections = sum(
            feedback_stats.get('corrections_by_category', {}).values()
        )

        production_accuracy = model_info.get('metrics', {}).get('accuracy', 0.85)

        # Check conditions for retraining
        if feedback_accuracy < settings.performance_threshold:
            needs_retraining = True
            reasons.append(
                f"Accuracy from feedback ({feedback_accuracy:.2f}) is below threshold ({settings.performance_threshold})"
            )

        if corrections > settings.correction_threshold:
            needs_retraining = True
            reasons.append(
                f"High volume of corrections received ({corrections} in recent period)"
            )

        # Determine recommendation
        if needs_retraining:
            recommendation = "trigger_retraining"
        else:
            recommendation = "no_action_needed"

        current_metrics = {
            'feedback_accuracy': feedback_accuracy,
            'production_accuracy': production_accuracy,
            'total_feedback': total_feedback,
            'correction_count': corrections
        }

        # Store check result
        with db.get_session() as session:
            check_record = RetrainingCheck(
                check_id=check_id,
                needs_retraining=needs_retraining,
                reasons=reasons,
                metrics=current_metrics,
                recommendation=recommendation
            )
            session.add(check_record)
            session.commit()

        logger.info(
            "Retrain check completed",
            correlation_id=correlation_id,
            needs_retraining=needs_retraining,
            recommendation=recommendation
        )

        return RetrainCheckResponse(
            needs_retraining=needs_retraining,
            reasons=reasons if reasons else ["Model performance is within acceptable thresholds"],
            current_metrics=current_metrics,
            recommendation=recommendation,
            last_check=datetime.utcnow().isoformat(),
            correlation_id=correlation_id
        )

    except Exception as e:
        logger.error("Retrain check failed", correlation_id=correlation_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Retrain check failed: {str(e)}",
                    "correlation_id": correlation_id
                }
            }
        )


@app.post("/api/v1/model/auto-retrain")
async def trigger_auto_retraining(
    background_tasks: BackgroundTasks,
    x_correlation_id: Optional[str] = Header(None)
):
    """Automatically check and trigger retraining if needed."""
    correlation_id = get_correlation_id(x_correlation_id)

    # First check if retraining is needed
    check_result = await check_retraining_needed(x_correlation_id)

    if not check_result.needs_retraining:
        return {
            "status": "skipped",
            "message": "Retraining not needed at this time",
            "reasons": check_result.reasons,
            "correlation_id": correlation_id
        }

    # Trigger training
    try:
        async with httpx.AsyncClient() as client:
            train_response = await client.post(
                f"{settings.model_service_url}/api/v1/model/train",
                json={"include_feedback": True},
                headers={"X-Correlation-ID": correlation_id},
                timeout=30.0
            )

            if train_response.status_code in [200, 201, 202]:
                train_result = train_response.json()
                return {
                    "status": "triggered",
                    "message": "Retraining triggered successfully",
                    "training_job_id": train_result.get('training_job_id'),
                    "reasons": check_result.reasons,
                    "correlation_id": correlation_id
                }
            else:
                raise Exception(f"Training service returned {train_response.status_code}")

    except Exception as e:
        logger.error("Failed to trigger retraining", correlation_id=correlation_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TRAINING_TRIGGER_FAILED",
                    "message": f"Failed to trigger retraining: {str(e)}",
                    "correlation_id": correlation_id
                }
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
