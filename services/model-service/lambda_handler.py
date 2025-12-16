"""
Lambda handler for Model Service
Handles model training and management via Lambda
"""

import json
import base64
from typing import Any, Dict
from mangum import Mangum
from app.main import app

# Mangum adapter for FastAPI -> Lambda
# Enable lifespan to initialize database and S3 client
handler = Mangum(app, lifespan="on")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function

    Note: For long-running training jobs, this triggers SageMaker
    instead of training in Lambda (which has 15-minute timeout)

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    response = handler(event, context)

    return response
