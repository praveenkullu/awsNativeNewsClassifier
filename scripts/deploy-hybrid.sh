#!/bin/bash
set -e

# Hybrid Architecture Deployment Script
# Deploys Lambda functions + ECS Inference service

ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🚀 Deploying Hybrid Architecture to $ENVIRONMENT environment"
echo "📍 Region: $AWS_REGION"
echo "🔑 Account: $AWS_ACCOUNT_ID"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# Step 1: Deploy Lambda Functions
# ============================================================================

echo -e "\n${BLUE}📦 Step 1: Packaging and deploying Lambda functions${NC}"

LAMBDA_SERVICES=("feedback-service" "model-service" "evaluation-service")

for service in "${LAMBDA_SERVICES[@]}"; do
    echo -e "${YELLOW}Deploying $service...${NC}"

    cd "services/$service"

    # Create deployment package
    mkdir -p package
    pip install -r requirements.txt -t package/ --quiet
    cp -r app package/
    cp lambda_handler.py package/

    # Create ZIP
    cd package
    zip -r ../lambda-deploy.zip . > /dev/null
    cd ..

    # Deploy to Lambda
    aws lambda update-function-code \
        --function-name "ml-news-${service%-service}-${ENVIRONMENT}" \
        --zip-file fileb://lambda-deploy.zip \
        --region "$AWS_REGION" \
        --publish > /dev/null

    echo -e "${GREEN}✅ $service deployed${NC}"

    # Cleanup
    rm -rf package lambda-deploy.zip
    cd ../..
done

# ============================================================================
# Step 2: Build and Push ECS Image
# ============================================================================

echo -e "\n${BLUE}🐳 Step 2: Building and pushing ECS Inference image${NC}"

# Login to ECR
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin \
    "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Build image
ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/ml-news-inference"
IMAGE_TAG="${ENVIRONMENT}-$(git rev-parse --short HEAD)"

echo "Building Docker image: ${ECR_REPO}:${IMAGE_TAG}"

docker build \
    -f services/inference-service/Dockerfile \
    -t "${ECR_REPO}:${IMAGE_TAG}" \
    -t "${ECR_REPO}:${ENVIRONMENT}-latest" \
    .

# Push to ECR
echo "Pushing to ECR..."
docker push "${ECR_REPO}:${IMAGE_TAG}"
docker push "${ECR_REPO}:${ENVIRONMENT}-latest"

echo -e "${GREEN}✅ ECS image pushed${NC}"

# ============================================================================
# Step 3: Update ECS Service
# ============================================================================

echo -e "\n${BLUE}🔄 Step 3: Updating ECS service${NC}"

# Get current task definition
TASK_FAMILY="ml-news-inference-${ENVIRONMENT}"
TASK_DEF=$(aws ecs describe-task-definition \
    --task-definition "$TASK_FAMILY" \
    --region "$AWS_REGION")

# Extract task definition without metadata
NEW_TASK_DEF=$(echo "$TASK_DEF" | jq '.taskDefinition |
    {
        family: .family,
        taskRoleArn: .taskRoleArn,
        executionRoleArn: .executionRoleArn,
        networkMode: .networkMode,
        containerDefinitions: .containerDefinitions,
        requiresCompatibilities: .requiresCompatibilities,
        cpu: .cpu,
        memory: .memory
    }')

# Update image in container definition
NEW_TASK_DEF=$(echo "$NEW_TASK_DEF" | jq \
    --arg IMAGE "${ECR_REPO}:${IMAGE_TAG}" \
    '.containerDefinitions[0].image = $IMAGE')

# Register new task definition
NEW_TASK_ARN=$(echo "$NEW_TASK_DEF" | \
    aws ecs register-task-definition \
        --cli-input-json file:///dev/stdin \
        --region "$AWS_REGION" | \
    jq -r '.taskDefinition.taskDefinitionArn')

echo "Registered new task definition: $NEW_TASK_ARN"

# Update ECS service
CLUSTER_NAME="ml-news-cluster-${ENVIRONMENT}"
SERVICE_NAME="ml-news-inference-${ENVIRONMENT}"

aws ecs update-service \
    --cluster "$CLUSTER_NAME" \
    --service "$SERVICE_NAME" \
    --task-definition "$NEW_TASK_ARN" \
    --region "$AWS_REGION" \
    --force-new-deployment > /dev/null

echo -e "${GREEN}✅ ECS service updated${NC}"

# Wait for deployment to complete
echo "Waiting for service to stabilize..."
aws ecs wait services-stable \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --region "$AWS_REGION"

echo -e "${GREEN}✅ Service deployment complete${NC}"

# ============================================================================
# Step 4: Smoke Tests
# ============================================================================

echo -e "\n${BLUE}🧪 Step 4: Running smoke tests${NC}"

# Get API Gateway URL from SSM or output
API_URL=$(aws ssm get-parameter \
    --name "/ml-news/${ENVIRONMENT}/api-url" \
    --query "Parameter.Value" \
    --output text \
    --region "$AWS_REGION" 2>/dev/null || echo "")

if [ -z "$API_URL" ]; then
    echo -e "${YELLOW}⚠️  API URL not found in SSM, skipping smoke tests${NC}"
else
    echo "Testing endpoint: $API_URL"

    # Health check
    if curl -f -s "${API_URL}/health" > /dev/null; then
        echo -e "${GREEN}✅ Health check passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Health check failed${NC}"
    fi

    # Prediction test
    PRED_RESPONSE=$(curl -s -X POST "${API_URL}/api/v1/predict" \
        -H "Content-Type: application/json" \
        -d '{"headline": "Stock market reaches new highs", "short_description": "Markets surge"}')

    if echo "$PRED_RESPONSE" | jq -e '.category' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Prediction endpoint working${NC}"
        echo "   Category: $(echo "$PRED_RESPONSE" | jq -r '.category')"
    else
        echo -e "${YELLOW}⚠️  Prediction endpoint may need model deployment${NC}"
    fi
fi

# ============================================================================
# Deployment Summary
# ============================================================================

echo -e "\n${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo ""
echo "Services deployed:"
echo "  ✅ Lambda: feedback-service"
echo "  ✅ Lambda: model-service"
echo "  ✅ Lambda: evaluation-service"
echo "  ✅ ECS: inference-service (${IMAGE_TAG})"
echo ""
if [ -n "$API_URL" ]; then
    echo "API Endpoint: $API_URL"
fi
echo ""
echo "Next steps:"
echo "  1. Monitor CloudWatch Logs"
echo "  2. Check metrics dashboard"
echo "  3. Deploy initial model if needed"
echo ""
