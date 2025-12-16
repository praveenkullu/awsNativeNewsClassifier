"""
Feedback Service - Collects and manages user feedback on predictions.
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from enum import Enum

import structlog
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Integer, Float, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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


class FeedbackRecord(Base):
    """Feedback database model."""

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_id = Column(String(100), unique=True, nullable=False, index=True)
    prediction_id = Column(String(100), nullable=False, index=True)
    predicted_category = Column(String(100))
    correct_category = Column(String(100))
    feedback_type = Column(String(50), nullable=False)
    user_id = Column(String(100))
    comment = Column(String(2000))
    headline = Column(String(500))
    model_version = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db

    logger.info("Starting Feedback Service")

    # Initialize database
    db = Database(settings.database_url)
    db.initialize()

    yield

    # Cleanup
    if db:
        db.close()
    logger.info("Feedback Service shutdown complete")


app = FastAPI(
    title="Feedback Service",
    description="Feedback collection and management service",
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
class FeedbackType(str, Enum):
    CORRECTION = "correction"
    CONFIRMATION = "confirmation"
    REJECTION = "rejection"


# Request/Response Models
class FeedbackRequest(BaseModel):
    prediction_id: str = Field(..., min_length=1)
    correct_category: Optional[str] = Field(None, max_length=100)
    feedback_type: FeedbackType
    user_id: Optional[str] = Field(None, max_length=100)
    comment: Optional[str] = Field(None, max_length=2000)
    predicted_category: Optional[str] = None
    headline: Optional[str] = None
    model_version: Optional[str] = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    prediction_id: str
    status: str
    timestamp: str
    correlation_id: str


class CategoryCorrections(BaseModel):
    category: str
    count: int


class FeedbackStatsResponse(BaseModel):
    period: Dict[str, str]
    total_predictions: int
    total_feedback: int
    feedback_rate: float
    accuracy_from_feedback: float
    corrections_by_category: Dict[str, int]
    correlation_id: str


class FeedbackItem(BaseModel):
    feedback_id: str
    prediction_id: str
    predicted_category: Optional[str]
    correct_category: Optional[str]
    feedback_type: str
    created_at: str


class FeedbackListResponse(BaseModel):
    items: List[FeedbackItem]
    total: int
    limit: int
    offset: int
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


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="feedback-service",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.post("/api/v1/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    request: FeedbackRequest,
    x_correlation_id: Optional[str] = Header(None)
):
    """Submit feedback on a prediction."""
    correlation_id = get_correlation_id(x_correlation_id)
    feedback_id = f"fb_{uuid.uuid4().hex[:12]}"

    logger.info(
        "Feedback received",
        correlation_id=correlation_id,
        prediction_id=request.prediction_id,
        feedback_type=request.feedback_type
    )

    # Validate correction feedback has correct_category
    if request.feedback_type == FeedbackType.CORRECTION and not request.correct_category:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "correct_category is required for correction feedback",
                    "correlation_id": correlation_id
                }
            }
        )

    # Store feedback
    try:
        with db.get_session() as session:
            feedback = FeedbackRecord(
                feedback_id=feedback_id,
                prediction_id=request.prediction_id,
                predicted_category=request.predicted_category,
                correct_category=request.correct_category,
                feedback_type=request.feedback_type.value,
                user_id=request.user_id,
                comment=request.comment,
                headline=request.headline,
                model_version=request.model_version
            )
            session.add(feedback)
            session.commit()

        logger.info(
            "Feedback stored",
            correlation_id=correlation_id,
            feedback_id=feedback_id
        )

        return FeedbackResponse(
            feedback_id=feedback_id,
            prediction_id=request.prediction_id,
            status="recorded",
            timestamp=datetime.utcnow().isoformat(),
            correlation_id=correlation_id
        )

    except Exception as e:
        logger.error("Failed to store feedback", correlation_id=correlation_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to store feedback",
                    "correlation_id": correlation_id
                }
            }
        )


@app.get("/api/v1/feedback/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    start_date: Optional[str] = Query(None, description="ISO 8601 date"),
    end_date: Optional[str] = Query(None, description="ISO 8601 date"),
    category: Optional[str] = Query(None),
    x_correlation_id: Optional[str] = Header(None)
):
    """Get feedback statistics."""
    correlation_id = get_correlation_id(x_correlation_id)

    # Parse dates
    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = datetime.utcnow() - timedelta(days=30)

        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid date format. Use ISO 8601.",
                    "correlation_id": correlation_id
                }
            }
        )

    try:
        with db.get_session() as session:
            # Base query
            query = session.query(FeedbackRecord).filter(
                FeedbackRecord.created_at >= start_dt,
                FeedbackRecord.created_at <= end_dt
            )

            if category:
                query = query.filter(
                    (FeedbackRecord.predicted_category == category) |
                    (FeedbackRecord.correct_category == category)
                )

            # Total feedback count
            total_feedback = query.count()

            # Confirmations (correct predictions)
            confirmations = query.filter(
                FeedbackRecord.feedback_type == FeedbackType.CONFIRMATION.value
            ).count()

            # Corrections count by category
            corrections_query = query.filter(
                FeedbackRecord.feedback_type == FeedbackType.CORRECTION.value
            )

            corrections_by_category = {}
            for record in corrections_query.all():
                cat = record.correct_category or "UNKNOWN"
                corrections_by_category[cat] = corrections_by_category.get(cat, 0) + 1

            # Calculate accuracy from feedback
            total_with_verdict = confirmations + len(
                [r for r in corrections_query.all()]
            )
            accuracy = confirmations / total_with_verdict if total_with_verdict > 0 else 0.0

            # Estimate total predictions (rough estimate)
            feedback_rate = 0.05  # Assume 5% feedback rate
            estimated_predictions = int(total_feedback / feedback_rate) if feedback_rate > 0 else 0

        return FeedbackStatsResponse(
            period={
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat()
            },
            total_predictions=estimated_predictions,
            total_feedback=total_feedback,
            feedback_rate=feedback_rate,
            accuracy_from_feedback=round(accuracy, 4),
            corrections_by_category=corrections_by_category,
            correlation_id=correlation_id
        )

    except Exception as e:
        logger.error("Failed to get feedback stats", correlation_id=correlation_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get feedback statistics",
                    "correlation_id": correlation_id
                }
            }
        )


@app.get("/api/v1/feedback", response_model=FeedbackListResponse)
async def list_feedback(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    feedback_type: Optional[str] = Query(None),
    prediction_id: Optional[str] = Query(None),
    x_correlation_id: Optional[str] = Header(None)
):
    """List feedback records."""
    correlation_id = get_correlation_id(x_correlation_id)

    try:
        with db.get_session() as session:
            query = session.query(FeedbackRecord)

            if feedback_type:
                query = query.filter(FeedbackRecord.feedback_type == feedback_type)

            if prediction_id:
                query = query.filter(FeedbackRecord.prediction_id == prediction_id)

            total = query.count()

            records = query.order_by(
                FeedbackRecord.created_at.desc()
            ).offset(offset).limit(limit).all()

            items = [
                FeedbackItem(
                    feedback_id=r.feedback_id,
                    prediction_id=r.prediction_id,
                    predicted_category=r.predicted_category,
                    correct_category=r.correct_category,
                    feedback_type=r.feedback_type,
                    created_at=r.created_at.isoformat()
                )
                for r in records
            ]

        return FeedbackListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            correlation_id=correlation_id
        )

    except Exception as e:
        logger.error("Failed to list feedback", correlation_id=correlation_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to list feedback",
                    "correlation_id": correlation_id
                }
            }
        )


@app.get("/api/v1/feedback/export")
async def export_feedback_for_training(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    x_correlation_id: Optional[str] = Header(None)
):
    """Export feedback data for model retraining."""
    correlation_id = get_correlation_id(x_correlation_id)

    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            start_dt = datetime.utcnow() - timedelta(days=30)

        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            end_dt = datetime.utcnow()

        with db.get_session() as session:
            # Get corrections for retraining
            corrections = session.query(FeedbackRecord).filter(
                FeedbackRecord.created_at >= start_dt,
                FeedbackRecord.created_at <= end_dt,
                FeedbackRecord.feedback_type == FeedbackType.CORRECTION.value,
                FeedbackRecord.correct_category.isnot(None),
                FeedbackRecord.headline.isnot(None)
            ).all()

            training_data = [
                {
                    "headline": r.headline,
                    "category": r.correct_category,
                    "source": "feedback",
                    "original_prediction": r.predicted_category,
                    "feedback_id": r.feedback_id
                }
                for r in corrections
            ]

        return {
            "period": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat()
            },
            "total_samples": len(training_data),
            "data": training_data,
            "correlation_id": correlation_id
        }

    except Exception as e:
        logger.error("Failed to export feedback", correlation_id=correlation_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to export feedback",
                    "correlation_id": correlation_id
                }
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
