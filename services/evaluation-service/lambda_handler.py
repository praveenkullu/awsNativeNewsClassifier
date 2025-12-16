"""
Lambda handler for Evaluation Service
Evaluates model performance and triggers retraining
"""

import json
from typing import Any, Dict
from mangum import Mangum
from app.main import app

# Mangum adapter for FastAPI -> Lambda
handler = Mangum(app, lifespan="off")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function

    Args:
        event: API Gateway event or EventBridge event
        context: Lambda context

    Returns:
        API Gateway response or evaluation result
    """
    # Check if this is an EventBridge scheduled event
    if event.get("source") == "aws.events":
        # Scheduled evaluation check
        # Import here to avoid cold start overhead
        from app.services.evaluation import run_scheduled_evaluation

        result = run_scheduled_evaluation()
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    # Otherwise, handle as API Gateway request
    response = handler(event, context)
    return response
