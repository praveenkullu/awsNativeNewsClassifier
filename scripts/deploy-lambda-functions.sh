#!/bin/bash
set -e

# Deploy Lambda Functions Script
# Packages and deploys the 3 Lambda functions for hybrid architecture

REGION="us-east-2"
LAMBDA_ROLE="arn:aws:iam::289140051471:role/ml-news-lambda-execution-role"
PRIV_SUBNET_1="subnet-0812a19c8a9e5200a"
PRIV_SUBNET_2="subnet-0448c720ac8783df3"
ECS_SG="sg-05df6c17bc1a67d66"

# Get RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier ml-news-db \
    --region $REGION \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)

echo "🚀 Deploying Lambda Functions"
echo "=============================="
echo "RDS Endpoint: $RDS_ENDPOINT"
echo ""

# Function to package and deploy a Lambda function
deploy_lambda() {
    local SERVICE_NAME=$1
    local FUNCTION_NAME=$2
    local DESCRIPTION=$3
    local MEMORY=$4
    local TIMEOUT=$5

    echo "📦 Packaging $SERVICE_NAME..."

    cd "services/$SERVICE_NAME"

    # Clean previous package
    rm -rf package lambda-deploy.zip
    mkdir -p package

    # Install dependencies
    echo "  Installing dependencies..."
    pip install -r requirements.txt -t package/ --quiet --upgrade

    # Add mangum for Lambda compatibility
    pip install mangum -t package/ --quiet

    # Copy application code
    cp -r app package/
    if [ -f "lambda_handler.py" ]; then
        cp lambda_handler.py package/
    fi

    # Create deployment package
    cd package
    zip -r ../lambda-deploy.zip . > /dev/null
    cd ..

    echo "  Package size: $(du -h lambda-deploy.zip | cut -f1)"

    # Check if function exists
    if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>/dev/null; then
        echo "  Updating existing function..."
        aws lambda update-function-code \
            --function-name $FUNCTION_NAME \
            --zip-file fileb://lambda-deploy.zip \
            --region $REGION > /dev/null

        aws lambda update-function-configuration \
            --function-name $FUNCTION_NAME \
            --timeout $TIMEOUT \
            --memory-size $MEMORY \
            --environment "Variables={DATABASE_URL=postgresql://mlnews:MLNews2024SecurePass!@$RDS_ENDPOINT:5432/mlnews,LOG_LEVEL=INFO}" \
            --region $REGION > /dev/null
    else
        echo "  Creating new function..."
        aws lambda create-function \
            --function-name $FUNCTION_NAME \
            --runtime python3.10 \
            --role $LAMBDA_ROLE \
            --handler lambda_handler.lambda_handler \
            --zip-file fileb://lambda-deploy.zip \
            --timeout $TIMEOUT \
            --memory-size $MEMORY \
            --description "$DESCRIPTION" \
            --environment "Variables={DATABASE_URL=postgresql://mlnews:MLNews2024SecurePass!@$RDS_ENDPOINT:5432/mlnews,LOG_LEVEL=INFO}" \
            --vpc-config SubnetIds=$PRIV_SUBNET_1,$PRIV_SUBNET_2,SecurityGroupIds=$ECS_SG \
            --region $REGION > /dev/null
    fi

    echo "✅ $FUNCTION_NAME deployed"

    # Cleanup
    rm -rf package lambda-deploy.zip
    cd ../..
}

# Deploy all Lambda functions
deploy_lambda "feedback-service" "ml-news-feedback" "Feedback collection service" 512 30
echo ""
deploy_lambda "model-service" "ml-news-model" "Model training and management" 2048 900
echo ""
deploy_lambda "evaluation-service" "ml-news-evaluation" "Model evaluation service" 1024 300

echo ""
echo "════════════════════════════════════════"
echo "✅ All Lambda Functions Deployed!"
echo "════════════════════════════════════════"
echo ""
echo "Functions:"
echo "  - ml-news-feedback (512MB, 30s)"
echo "  - ml-news-model (2GB, 15min)"
echo "  - ml-news-evaluation (1GB, 5min)"
echo ""
echo "Next step: ./scripts/setup-api-gateway.sh"
echo ""
