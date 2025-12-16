# API Specifications

## Overview

All API endpoints are accessed through the API Gateway at `http://localhost:8000` (development) or your AWS endpoint (production).

### Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | `application/json` |
| `X-Correlation-ID` | No | Request tracking ID (auto-generated if not provided) |
| `Authorization` | Conditional | Bearer token for protected endpoints |

### Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {},
    "correlation_id": "uuid-string"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Downstream service unavailable |

---

## Health Check Endpoints

### GET /health

Check service health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "api-gateway",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "dependencies": {
    "inference_service": "healthy",
    "feedback_service": "healthy",
    "model_service": "healthy",
    "evaluation_service": "healthy"
  }
}
```

---

## Inference Endpoints

### POST /api/v1/predict

Classify a news article into categories.

**Request Body:**
```json
{
  "headline": "string (required, max 500 chars)",
  "short_description": "string (optional, max 2000 chars)",
  "request_id": "string (optional, for tracking)"
}
```

**Success Response (200):**
```json
{
  "prediction_id": "pred_abc123xyz",
  "category": "BUSINESS",
  "confidence": 0.87,
  "top_categories": [
    {"category": "BUSINESS", "confidence": 0.87},
    {"category": "MONEY", "confidence": 0.08},
    {"category": "POLITICS", "confidence": 0.03}
  ],
  "model_version": "v1.2.0",
  "processing_time_ms": 45,
  "correlation_id": "corr_def456"
}
```

**Error Response (400):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Headline is required and must be a non-empty string",
    "details": {
      "field": "headline",
      "constraint": "required"
    },
    "correlation_id": "corr_def456"
  }
}
```

### POST /api/v1/predict/batch

Classify multiple news articles (max 100 per request).

**Request Body:**
```json
{
  "articles": [
    {
      "id": "article_001",
      "headline": "Stock markets surge...",
      "short_description": "..."
    },
    {
      "id": "article_002",
      "headline": "New technology breakthrough...",
      "short_description": "..."
    }
  ]
}
```

**Success Response (200):**
```json
{
  "batch_id": "batch_xyz789",
  "results": [
    {
      "id": "article_001",
      "prediction_id": "pred_001",
      "category": "BUSINESS",
      "confidence": 0.92,
      "status": "success"
    },
    {
      "id": "article_002",
      "prediction_id": "pred_002",
      "category": "TECH",
      "confidence": 0.88,
      "status": "success"
    }
  ],
  "model_version": "v1.2.0",
  "total_processing_time_ms": 120,
  "correlation_id": "corr_ghi789"
}
```

---

## Feedback Endpoints

### POST /api/v1/feedback

Submit feedback on a prediction.

**Request Body:**
```json
{
  "prediction_id": "pred_abc123xyz",
  "correct_category": "POLITICS",
  "feedback_type": "correction",
  "user_id": "user_optional",
  "comment": "optional comment"
}
```

**Feedback Types:**
- `correction`: User corrects the predicted category
- `confirmation`: User confirms the prediction was correct
- `rejection`: User indicates the prediction was wrong (no correction provided)

**Success Response (201):**
```json
{
  "feedback_id": "fb_jkl012",
  "prediction_id": "pred_abc123xyz",
  "status": "recorded",
  "timestamp": "2024-01-15T10:35:00Z",
  "correlation_id": "corr_mno345"
}
```

### GET /api/v1/feedback/stats

Get feedback statistics.

**Query Parameters:**
- `start_date`: ISO 8601 date (optional)
- `end_date`: ISO 8601 date (optional)
- `category`: Filter by category (optional)

**Success Response (200):**
```json
{
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-15T23:59:59Z"
  },
  "total_predictions": 10000,
  "total_feedback": 500,
  "feedback_rate": 0.05,
  "accuracy_from_feedback": 0.82,
  "corrections_by_category": {
    "POLITICS": 45,
    "BUSINESS": 32,
    "ENTERTAINMENT": 28
  },
  "correlation_id": "corr_pqr678"
}
```

---

## Model Management Endpoints

### POST /api/v1/model/train

Trigger model training.

**Request Body:**
```json
{
  "include_feedback": true,
  "config": {
    "epochs": 10,
    "batch_size": 32,
    "learning_rate": 0.001
  },
  "description": "Retraining with latest feedback data"
}
```

**Success Response (202 - Accepted):**
```json
{
  "training_job_id": "train_stu901",
  "status": "queued",
  "estimated_duration_minutes": 30,
  "message": "Training job queued successfully",
  "correlation_id": "corr_vwx234"
}
```

### GET /api/v1/model/train/{job_id}

Get training job status.

**Success Response (200):**
```json
{
  "training_job_id": "train_stu901",
  "status": "running",
  "progress": 0.65,
  "current_epoch": 7,
  "total_epochs": 10,
  "metrics": {
    "current_loss": 0.234,
    "current_accuracy": 0.81
  },
  "started_at": "2024-01-15T10:00:00Z",
  "estimated_completion": "2024-01-15T10:25:00Z",
  "correlation_id": "corr_yza567"
}
```

**Training Job Statuses:**
- `queued`: Job waiting to start
- `running`: Training in progress
- `completed`: Training finished successfully
- `failed`: Training failed
- `cancelled`: Job was cancelled

### GET /api/v1/model/versions

List all model versions.

**Query Parameters:**
- `limit`: Number of results (default: 10, max: 100)
- `offset`: Pagination offset (default: 0)
- `status`: Filter by status (active, archived, pending)

**Success Response (200):**
```json
{
  "versions": [
    {
      "version": "v1.2.0",
      "status": "active",
      "created_at": "2024-01-15T10:30:00Z",
      "metrics": {
        "accuracy": 0.85,
        "f1_score": 0.83,
        "precision": 0.84,
        "recall": 0.82
      },
      "training_job_id": "train_stu901",
      "is_production": true
    },
    {
      "version": "v1.1.0",
      "status": "archived",
      "created_at": "2024-01-01T08:00:00Z",
      "metrics": {
        "accuracy": 0.82,
        "f1_score": 0.80
      },
      "training_job_id": "train_old123",
      "is_production": false
    }
  ],
  "total": 5,
  "limit": 10,
  "offset": 0,
  "correlation_id": "corr_bcd890"
}
```

### POST /api/v1/model/deploy/{version}

Deploy a specific model version to production.

**Success Response (200):**
```json
{
  "version": "v1.2.0",
  "status": "deploying",
  "message": "Model deployment initiated",
  "previous_version": "v1.1.0",
  "correlation_id": "corr_efg123"
}
```

---

## Evaluation Endpoints

### POST /api/v1/model/evaluate

Evaluate a model version.

**Request Body:**
```json
{
  "version": "v1.2.0",
  "test_data_source": "holdout",
  "include_feedback_data": true
}
```

**Test Data Sources:**
- `holdout`: Use held-out test set
- `feedback`: Use corrected feedback data
- `both`: Combine holdout and feedback data

**Success Response (202 - Accepted):**
```json
{
  "evaluation_id": "eval_hij456",
  "version": "v1.2.0",
  "status": "running",
  "message": "Evaluation started",
  "correlation_id": "corr_klm789"
}
```

### GET /api/v1/model/evaluate/{evaluation_id}

Get evaluation results.

**Success Response (200):**
```json
{
  "evaluation_id": "eval_hij456",
  "version": "v1.2.0",
  "status": "completed",
  "metrics": {
    "accuracy": 0.856,
    "precision": 0.842,
    "recall": 0.838,
    "f1_score": 0.840,
    "confusion_matrix": "s3://bucket/eval_hij456/confusion_matrix.json"
  },
  "category_metrics": {
    "POLITICS": {"precision": 0.89, "recall": 0.87, "f1": 0.88},
    "BUSINESS": {"precision": 0.85, "recall": 0.83, "f1": 0.84}
  },
  "comparison_with_production": {
    "accuracy_diff": 0.012,
    "f1_diff": 0.015,
    "recommendation": "deploy",
    "meets_threshold": true
  },
  "completed_at": "2024-01-15T11:00:00Z",
  "correlation_id": "corr_nop012"
}
```

### POST /api/v1/model/retrain-check

Check if retraining is needed based on feedback and performance.

**Success Response (200):**
```json
{
  "needs_retraining": true,
  "reasons": [
    "Accuracy dropped below threshold (0.75) to 0.72",
    "High volume of corrections received (150 in last 7 days)"
  ],
  "current_metrics": {
    "feedback_accuracy": 0.72,
    "production_accuracy": 0.85,
    "correction_rate": 0.08
  },
  "recommendation": "trigger_retraining",
  "last_check": "2024-01-15T11:30:00Z",
  "correlation_id": "corr_qrs345"
}
```

---

## Categories

Available news categories (41 total):

```json
[
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
```

---

## Rate Limits

| Endpoint | Rate Limit |
|----------|------------|
| `/api/v1/predict` | 100 requests/minute |
| `/api/v1/predict/batch` | 10 requests/minute |
| `/api/v1/feedback` | 50 requests/minute |
| `/api/v1/model/*` | 10 requests/minute |

Rate limit headers in response:
- `X-RateLimit-Limit`: Request limit
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Webhooks (Optional)

Configure webhooks to receive notifications for events.

### Available Events

- `training.started`
- `training.completed`
- `training.failed`
- `evaluation.completed`
- `model.deployed`
- `retraining.recommended`

### Webhook Payload Example

```json
{
  "event": "training.completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "training_job_id": "train_stu901",
    "version": "v1.2.0",
    "metrics": {
      "accuracy": 0.85
    }
  },
  "correlation_id": "corr_tuv678"
}
```
