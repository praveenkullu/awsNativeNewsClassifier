"""
Lambda handler for Feedback Service
Adapts FastAPI application to work with AWS Lambda + API Gateway
"""

import json
import base64
from typing import Any, Dict
from mangum import Mangum
from app.main import app, db, Database
from app.config import settings

# Initialize database globally (since lifespan is off in Lambda)
if db is None:
    from app import main as app_main
    app_main.db = Database(settings.database_url)
    app_main.db.initialize()

# Mangum adapter for FastAPI -> Lambda
handler = Mangum(app, lifespan="off")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    # Mangum handles the conversion from Lambda event to FastAPI request
    response = handler(event, context)

    return response
