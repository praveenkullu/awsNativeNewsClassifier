"""
API Gateway Service - Routes requests to microservices.
"""
import os
import uuid
import time
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# HTTP client
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global http_client

    logger.info("Starting API Gateway")

    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)

    yield

    # Cleanup
    if http_client:
        await http_client.aclose()
    logger.info("API Gateway shutdown complete")


app = FastAPI(
    title="ML News Categorization API",
    description="API Gateway for news categorization ML pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files serving for web interface
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Mount static files if directory exists
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info("Static files directory mounted", path=STATIC_DIR)


# Request/Response Models
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str
    dependencies: Dict[str, str]


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


# Middleware for logging and correlation ID
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Add logging and correlation ID to all requests."""
    start_time = time.time()

    # Get or generate correlation ID
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

    # Add to request state
    request.state.correlation_id = correlation_id

    logger.info(
        "Request started",
        correlation_id=correlation_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown"
    )

    try:
        response = await call_next(request)

        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = correlation_id

        # Log completion
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Request completed",
            correlation_id=correlation_id,
            status_code=response.status_code,
            duration_ms=duration_ms
        )

        return response

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Request failed",
            correlation_id=correlation_id,
            error=str(e),
            duration_ms=duration_ms
        )
        raise


# Helper functions
def get_correlation_id(request: Request) -> str:
    """Get correlation ID from request."""
    return getattr(request.state, 'correlation_id', str(uuid.uuid4()))


async def proxy_request(
    service_url: str,
    path: str,
    method: str,
    request: Request,
    body: Optional[bytes] = None
) -> Response:
    """Proxy request to downstream service."""
    correlation_id = get_correlation_id(request)

    url = f"{service_url}{path}"

    headers = {
        "X-Correlation-ID": correlation_id,
        "Content-Type": request.headers.get("Content-Type", "application/json")
    }

    try:
        if method == "GET":
            response = await http_client.get(url, headers=headers, params=dict(request.query_params))
        elif method == "POST":
            response = await http_client.post(url, headers=headers, content=body)
        elif method == "PUT":
            response = await http_client.put(url, headers=headers, content=body)
        elif method == "DELETE":
            response = await http_client.delete(url, headers=headers)
        else:
            raise HTTPException(status_code=405, detail="Method not allowed")

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={
                "Content-Type": response.headers.get("Content-Type", "application/json"),
                "X-Correlation-ID": correlation_id
            }
        )

    except httpx.TimeoutException:
        logger.error("Service timeout", service_url=service_url, path=path)
        raise HTTPException(
            status_code=504,
            detail={
                "error": {
                    "code": "SERVICE_TIMEOUT",
                    "message": "Downstream service timeout",
                    "correlation_id": correlation_id
                }
            }
        )
    except httpx.ConnectError:
        logger.error("Service unavailable", service_url=service_url, path=path)
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Downstream service unavailable",
                    "correlation_id": correlation_id
                }
            }
        )


async def check_service_health(service_url: str, service_name: str) -> str:
    """Check health of a downstream service."""
    try:
        response = await http_client.get(f"{service_url}/health", timeout=5.0)
        if response.status_code == 200:
            return "healthy"
        return "unhealthy"
    except Exception:
        return "unavailable"


# Health Check Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check including all dependencies."""
    # Check all downstream services
    dependencies = {}

    service_checks = [
        (settings.inference_service_url, "inference_service"),
        (settings.feedback_service_url, "feedback_service"),
        (settings.model_service_url, "model_service"),
        (settings.evaluation_service_url, "evaluation_service"),
    ]

    for url, name in service_checks:
        dependencies[name] = await check_service_health(url, name)

    # Determine overall status
    all_healthy = all(status == "healthy" for status in dependencies.values())
    status = "healthy" if all_healthy else "degraded"

    return HealthResponse(
        status=status,
        service="api-gateway",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        dependencies=dependencies
    )


@app.get("/health/live")
async def liveness_check():
    """Simple liveness check."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_check():
    """Readiness check - ensures service can handle requests."""
    # Quick check of critical dependencies
    inference_health = await check_service_health(
        settings.inference_service_url,
        "inference_service"
    )

    if inference_health != "healthy":
        raise HTTPException(status_code=503, detail="Not ready - inference service unavailable")

    return {"status": "ready"}


# Inference Routes
@app.post("/api/v1/predict")
@limiter.limit("100/minute")
async def predict(request: Request):
    """Route prediction requests to inference service."""
    body = await request.body()
    return await proxy_request(
        settings.inference_service_url,
        "/api/v1/predict",
        "POST",
        request,
        body
    )


@app.post("/api/v1/predict/batch")
@limiter.limit("10/minute")
async def predict_batch(request: Request):
    """Route batch prediction requests to inference service."""
    body = await request.body()
    return await proxy_request(
        settings.inference_service_url,
        "/api/v1/predict/batch",
        "POST",
        request,
        body
    )


# Feedback Routes
@app.post("/api/v1/feedback")
@limiter.limit("50/minute")
async def submit_feedback(request: Request):
    """Route feedback submission to feedback service."""
    body = await request.body()
    return await proxy_request(
        settings.feedback_service_url,
        "/api/v1/feedback",
        "POST",
        request,
        body
    )


@app.get("/api/v1/feedback/stats")
@limiter.limit("20/minute")
async def get_feedback_stats(request: Request):
    """Route feedback stats request to feedback service."""
    return await proxy_request(
        settings.feedback_service_url,
        "/api/v1/feedback/stats",
        "GET",
        request
    )


@app.get("/api/v1/feedback")
@limiter.limit("20/minute")
async def list_feedback(request: Request):
    """Route feedback list request to feedback service."""
    return await proxy_request(
        settings.feedback_service_url,
        "/api/v1/feedback",
        "GET",
        request
    )


# Model Routes
@app.post("/api/v1/model/train")
@limiter.limit("5/minute")
async def trigger_training(request: Request):
    """Route training request to model service."""
    body = await request.body()
    return await proxy_request(
        settings.model_service_url,
        "/api/v1/model/train",
        "POST",
        request,
        body
    )


@app.get("/api/v1/model/train/{job_id}")
@limiter.limit("20/minute")
async def get_training_status(job_id: str, request: Request):
    """Route training status request to model service."""
    return await proxy_request(
        settings.model_service_url,
        f"/api/v1/model/train/{job_id}",
        "GET",
        request
    )


@app.get("/api/v1/model/versions")
@limiter.limit("20/minute")
async def list_model_versions(request: Request):
    """Route model versions request to model service."""
    return await proxy_request(
        settings.model_service_url,
        "/api/v1/model/versions",
        "GET",
        request
    )


@app.post("/api/v1/model/deploy/{version}")
@limiter.limit("5/minute")
async def deploy_model(version: str, request: Request):
    """Route model deployment request to model service."""
    return await proxy_request(
        settings.model_service_url,
        f"/api/v1/model/deploy/{version}",
        "POST",
        request
    )


# Evaluation Routes
@app.post("/api/v1/model/evaluate")
@limiter.limit("10/minute")
async def evaluate_model(request: Request):
    """Route evaluation request to evaluation service."""
    body = await request.body()
    return await proxy_request(
        settings.evaluation_service_url,
        "/api/v1/model/evaluate",
        "POST",
        request,
        body
    )


@app.get("/api/v1/model/evaluate/{evaluation_id}")
@limiter.limit("20/minute")
async def get_evaluation_result(evaluation_id: str, request: Request):
    """Route evaluation result request to evaluation service."""
    return await proxy_request(
        settings.evaluation_service_url,
        f"/api/v1/model/evaluate/{evaluation_id}",
        "GET",
        request
    )


@app.post("/api/v1/model/retrain-check")
@limiter.limit("10/minute")
async def check_retraining(request: Request):
    """Route retrain check request to evaluation service."""
    return await proxy_request(
        settings.evaluation_service_url,
        "/api/v1/model/retrain-check",
        "POST",
        request
    )


# Info endpoint
@app.get("/api/v1/info")
async def get_api_info():
    """Get API information."""
    return {
        "name": "ML News Categorization API",
        "version": "1.0.0",
        "description": "Real-time news article categorization using machine learning",
        "endpoints": {
            "predict": "/api/v1/predict",
            "batch_predict": "/api/v1/predict/batch",
            "feedback": "/api/v1/feedback",
            "feedback_stats": "/api/v1/feedback/stats",
            "train": "/api/v1/model/train",
            "model_versions": "/api/v1/model/versions",
            "evaluate": "/api/v1/model/evaluate",
            "retrain_check": "/api/v1/model/retrain-check"
        },
        "categories": [
            "POLITICS", "WELLNESS", "ENTERTAINMENT", "TRAVEL", "STYLE & BEAUTY",
            "PARENTING", "HEALTHY LIVING", "QUEER VOICES", "FOOD & DRINK", "BUSINESS",
            "COMEDY", "SPORTS", "BLACK VOICES", "HOME & LIVING", "PARENTS",
            "THE WORLDPOST", "WEDDINGS", "WOMEN", "IMPACT", "DIVORCE",
            "CRIME", "MEDIA", "WEIRD NEWS", "GREEN", "WORLDPOST",
            "RELIGION", "STYLE", "SCIENCE", "WORLD NEWS", "TASTE",
            "TECH", "MONEY", "ARTS", "FIFTY", "GOOD NEWS",
            "ARTS & CULTURE", "ENVIRONMENT", "COLLEGE", "LATINO VOICES",
            "CULTURE & ARTS", "EDUCATION"
        ]
    }


# Root route - Serve web interface
@app.get("/", include_in_schema=False)
async def root():
    """Serve the web interface."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "message": "ML News Categorization API",
        "docs": "/docs",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
