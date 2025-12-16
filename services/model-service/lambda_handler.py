"""
Lambda handler for Model Service
Handles model training and management via Lambda
"""

import json
import base64
import boto3
from typing import Any, Dict
from mangum import Mangum
from app.main import app, s3_client as app_s3_client
from app.config import settings

# Initialize S3 client at module level (database not accessible from Lambda)
if app_s3_client is None and settings.aws_region:
    import app.main as main_module
    main_module.s3_client = boto3.client('s3', region_name=settings.aws_region)

# Mangum adapter for FastAPI -> Lambda
# Keep lifespan off since database is not accessible from Lambda (VPC issue)
handler = Mangum(app, lifespan="off")


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
