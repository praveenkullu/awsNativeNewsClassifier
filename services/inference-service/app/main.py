"""
Inference Service - Handles real-time predictions for news categorization.
"""
import os
import uuid
import pickle
import hashlib
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import structlog
import numpy as np
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import redis
import httpx
import boto3
from botocore.exceptions import ClientError

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
model = None
preprocessor = None
model_version = "default"
redis_client: Optional[redis.Redis] = None
s3_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global model, model_version, redis_client, s3_client

    logger.info("Starting Inference Service")

    # Initialize Redis client
    try:
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=0,
            decode_responses=False
        )
        redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning("Redis connection failed, caching disabled", error=str(e))
        redis_client = None

    # Initialize S3 client
    if settings.aws_region:
        try:
            s3_client = boto3.client('s3', region_name=settings.aws_region)
        except Exception as e:
            logger.warning("S3 client initialization failed", error=str(e))

    # Load model
    await load_model()

    yield

    # Cleanup
    if redis_client:
        redis_client.close()
    logger.info("Inference Service shutdown complete")


async def load_model(version: Optional[str] = None):
    """Load model from file or S3."""
    global model, preprocessor, model_version

    try:
        # Try to get model info from model service
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{settings.model_service_url}/api/v1/model/active",
                    timeout=10.0
                )
                if response.status_code == 200:
                    model_info = response.json()
                    model_path = model_info.get('model_path')
                    model_version = model_info.get('version', 'default')
                    logger.info("Got model info from model service", version=model_version)
            except Exception as e:
                logger.warning("Failed to get model info from service", error=str(e))
                model_path = settings.default_model_path

        # Load model from file
        if model_path and os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
                model = model_data.get('pipeline') or model_data
                preprocessor = model_data.get('preprocessor')
            logger.info("Model loaded from file", path=model_path, version=model_version)
        else:
            # Try S3 if configured
            if s3_client and settings.s3_model_bucket:
                try:
                    s3_key = f"models/{version or 'latest'}/model.pkl"
                    local_path = f"/tmp/model_{version or 'latest'}.pkl"

                    s3_client.download_file(
                        settings.s3_model_bucket,
                        s3_key,
                        local_path
                    )

                    with open(local_path, 'rb') as f:
                        model_data = pickle.load(f)
                        model = model_data.get('pipeline') or model_data
                        preprocessor = model_data.get('preprocessor')

                    logger.info("Model loaded from S3", bucket=settings.s3_model_bucket)
                except ClientError as e:
                    logger.warning("Failed to load model from S3", error=str(e))

        if model is None:
            logger.warning("No model loaded, predictions will fail")

    except Exception as e:
        logger.error("Error loading model", error=str(e))


app = FastAPI(
    title="Inference Service",
    description="Real-time news categorization predictions",
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
class PredictRequest(BaseModel):
    headline: str = Field(..., min_length=1, max_length=500)
    short_description: Optional[str] = Field(None, max_length=2000)
    request_id: Optional[str] = None

    @field_validator('headline')
    @classmethod
    def validate_headline(cls, v):
        if not v or not v.strip():
            raise ValueError("Headline must not be empty")
        return v.strip()


class CategoryScore(BaseModel):
    category: str
    confidence: float


class PredictResponse(BaseModel):
    prediction_id: str
    category: str
    confidence: float
    top_categories: List[CategoryScore]
    model_version: str
    processing_time_ms: int
    correlation_id: str


class BatchArticle(BaseModel):
    id: str
    headline: str = Field(..., min_length=1, max_length=500)
    short_description: Optional[str] = Field(None, max_length=2000)


class BatchPredictRequest(BaseModel):
    articles: List[BatchArticle] = Field(..., max_length=100)


class BatchPredictResult(BaseModel):
    id: str
    prediction_id: str
    category: str
    confidence: float
    status: str


class BatchPredictResponse(BaseModel):
    batch_id: str
    results: List[BatchPredictResult]
    model_version: str
    total_processing_time_ms: int
    correlation_id: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str
    model_loaded: bool
    model_version: str


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


# Helper functions
def get_correlation_id(x_correlation_id: Optional[str] = None) -> str:
    """Get or generate correlation ID."""
    return x_correlation_id or str(uuid.uuid4())


def get_cache_key(headline: str, description: Optional[str] = None) -> str:
    """Generate cache key for prediction."""
    text = f"{headline}:{description or ''}"
    return f"pred:{hashlib.md5(text.encode()).hexdigest()}"


def preprocess_text(headline: str, description: Optional[str] = None) -> str:
    """Preprocess text for prediction."""
    import re

    text = headline.lower()
    if description:
        text = f"{text} {description.lower()}"

    # Remove URLs
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)

    # Remove special characters
    text = re.sub(r'[^a-zA-Z0-9\s\'\-]', ' ', text)

    # Remove extra whitespace
    text = ' '.join(text.split())

    return text.strip()


def predict_single(text: str) -> Dict[str, Any]:
    """Make prediction for single text."""
    if model is None:
        raise RuntimeError("Model not loaded")

    predictions = model.predict([text])
    probabilities = model.predict_proba([text])

    predicted_category = predictions[0]  # Already a category name
    probs = probabilities[0]

    # Get category names from model classes
    categories = model.classes_

    # Find the index of the predicted category
    pred_idx = np.where(categories == predicted_category)[0][0]

    # Get top categories
    top_indices = np.argsort(probs)[::-1][:5]
    top_categories = []

    for idx in top_indices:
        category_name = categories[idx]
        top_categories.append({
            'category': category_name,
            'confidence': float(probs[idx])
        })

    return {
        'category': predicted_category,
        'confidence': float(probs[pred_idx]),
        'top_categories': top_categories
    }


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check endpoint."""
    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        service="inference-service",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        model_loaded=model is not None,
        model_version=model_version
    )


@app.get("/api/v1/info")
async def get_info():
    """Get API information including available categories."""
    categories = []
    if model is not None and hasattr(model, 'classes_'):
        categories = model.classes_.tolist()

    return {
        "service": "ml-news-categorization",
        "version": "1.0.0",
        "model_version": model_version,
        "model_loaded": model is not None,
        "categories": categories,
        "total_categories": len(categories)
    }


@app.post("/api/v1/predict", response_model=PredictResponse, responses={400: {"model": ErrorResponse}})
async def predict(
    request: PredictRequest,
    x_correlation_id: Optional[str] = Header(None)
):
    """Classify a news article into categories."""
    start_time = time.time()
    correlation_id = get_correlation_id(x_correlation_id)
    prediction_id = f"pred_{uuid.uuid4().hex[:12]}"

    logger.info(
        "Prediction request received",
        correlation_id=correlation_id,
        headline_length=len(request.headline)
    )

    if model is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "MODEL_NOT_LOADED",
                    "message": "Model is not loaded. Please wait or trigger training.",
                    "correlation_id": correlation_id
                }
            }
        )

    # Check cache
    cache_key = get_cache_key(request.headline, request.short_description)
    cached_result = None

    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                cached_result = pickle.loads(cached_data)
                logger.info("Cache hit", correlation_id=correlation_id)
        except Exception as e:
            logger.warning("Cache read failed", error=str(e))

    if cached_result:
        processing_time_ms = int((time.time() - start_time) * 1000)
        return PredictResponse(
            prediction_id=prediction_id,
            category=cached_result['category'],
            confidence=cached_result['confidence'],
            top_categories=[
                CategoryScore(**cat) for cat in cached_result['top_categories']
            ],
            model_version=model_version,
            processing_time_ms=processing_time_ms,
            correlation_id=correlation_id
        )

    # Preprocess and predict
    try:
        processed_text = preprocess_text(request.headline, request.short_description)
        result = predict_single(processed_text)

        # Cache result
        if redis_client:
            try:
                redis_client.setex(
                    cache_key,
                    settings.cache_ttl_seconds,
                    pickle.dumps(result)
                )
            except Exception as e:
                logger.warning("Cache write failed", error=str(e))

        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "Prediction completed",
            correlation_id=correlation_id,
            prediction_id=prediction_id,
            category=result['category'],
            confidence=result['confidence'],
            processing_time_ms=processing_time_ms
        )

        return PredictResponse(
            prediction_id=prediction_id,
            category=result['category'],
            confidence=result['confidence'],
            top_categories=[
                CategoryScore(**cat) for cat in result['top_categories']
            ],
            model_version=model_version,
            processing_time_ms=processing_time_ms,
            correlation_id=correlation_id
        )

    except Exception as e:
        logger.error("Prediction failed", correlation_id=correlation_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "PREDICTION_ERROR",
                    "message": f"Prediction failed: {str(e)}",
                    "correlation_id": correlation_id
                }
            }
        )


@app.post("/api/v1/predict/batch", response_model=BatchPredictResponse)
async def predict_batch(
    request: BatchPredictRequest,
    x_correlation_id: Optional[str] = Header(None)
):
    """Classify multiple news articles."""
    start_time = time.time()
    correlation_id = get_correlation_id(x_correlation_id)
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"

    logger.info(
        "Batch prediction request received",
        correlation_id=correlation_id,
        batch_size=len(request.articles)
    )

    if model is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "MODEL_NOT_LOADED",
                    "message": "Model is not loaded",
                    "correlation_id": correlation_id
                }
            }
        )

    results = []

    for article in request.articles:
        prediction_id = f"pred_{uuid.uuid4().hex[:12]}"
        try:
            processed_text = preprocess_text(article.headline, article.short_description)
            result = predict_single(processed_text)

            results.append(BatchPredictResult(
                id=article.id,
                prediction_id=prediction_id,
                category=result['category'],
                confidence=result['confidence'],
                status="success"
            ))
        except Exception as e:
            results.append(BatchPredictResult(
                id=article.id,
                prediction_id=prediction_id,
                category="UNKNOWN",
                confidence=0.0,
                status=f"error: {str(e)}"
            ))

    processing_time_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "Batch prediction completed",
        correlation_id=correlation_id,
        batch_id=batch_id,
        total_processing_time_ms=processing_time_ms
    )

    return BatchPredictResponse(
        batch_id=batch_id,
        results=results,
        model_version=model_version,
        total_processing_time_ms=processing_time_ms,
        correlation_id=correlation_id
    )


@app.post("/api/v1/reload-model")
async def reload_model(
    version: Optional[str] = None,
    x_correlation_id: Optional[str] = Header(None)
):
    """Reload the model (admin endpoint)."""
    correlation_id = get_correlation_id(x_correlation_id)

    logger.info("Model reload requested", correlation_id=correlation_id, version=version)

    await load_model(version)

    return {
        "status": "success",
        "message": "Model reload initiated",
        "model_version": model_version,
        "correlation_id": correlation_id
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
