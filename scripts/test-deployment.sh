#!/bin/bash
set -e

# Test Deployment Script
# Runs end-to-end tests on the deployed system

REGION="us-east-2"

echo "🧪 Testing ML News Deployment"
echo "=============================="

# Get API endpoint
API_ID=$(aws apigatewayv2 get-apis --region $REGION --query 'Items[?Name==`ml-news-api`].ApiId' --output text)
if [ -z "$API_ID" ]; then
    echo "❌ API Gateway not found. Run setup-api-gateway.sh first."
    exit 1
fi

API_ENDPOINT=$(aws apigatewayv2 get-api --api-id $API_ID --region $REGION --query 'ApiEndpoint' --output text)
echo "API Endpoint: $API_ENDPOINT"
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
if curl -f -s "$API_ENDPOINT/health" > /dev/null; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi
echo ""

# Test 2: Prediction (will fail without trained model, but tests API connectivity)
echo "Test 2: Prediction API"
echo "----------------------"
PRED_RESPONSE=$(curl -s -X POST "$API_ENDPOINT/api/v1/predict" \
    -H "Content-Type: application/json" \
    -d '{
        "headline": "Stock market reaches new highs amid economic recovery",
        "short_description": "Markets surge on positive GDP data"
    }')

echo "Response: $PRED_RESPONSE"
if echo "$PRED_RESPONSE" | jq -e . > /dev/null 2>&1; then
    echo "✅ Prediction API responding (JSON valid)"
else
    echo "⚠️  Prediction API may need model deployment"
fi
echo ""

# Test 3: Feedback API
echo "Test 3: Feedback API"
echo "--------------------"
FEEDBACK_RESPONSE=$(curl -s -X POST "$API_ENDPOINT/api/v1/feedback" \
    -H "Content-Type: application/json" \
    -d '{
        "prediction_id": "test-123",
        "feedback_type": "confirmation",
        "correct_category": "BUSINESS"
    }' || echo "{}")

echo "Response: $FEEDBACK_RESPONSE"
if echo "$FEEDBACK_RESPONSE" | jq -e . > /dev/null 2>&1; then
    echo "✅ Feedback API responding"
else
    echo "⚠️  Feedback API issue"
fi
echo ""

# Test 4: Model Service API
echo "Test 4: Model Service API"
echo "-------------------------"
VERSIONS_RESPONSE=$(curl -s "$API_ENDPOINT/api/v1/model/versions" || echo "{}")

echo "Response: $VERSIONS_RESPONSE"
if echo "$VERSIONS_RESPONSE" | jq -e . > /dev/null 2>&1; then
    echo "✅ Model Service API responding"
else
    echo "⚠️  Model Service API issue"
fi
echo ""

# Test 5: Check ECS Service
echo "Test 5: ECS Service Status"
echo "--------------------------"
ECS_STATUS=$(aws ecs describe-services \
    --cluster ml-news-cluster \
    --services ml-news-inference-service \
    --region $REGION \
    --query 'services[0].[runningCount,desiredCount]' \
    --output text)

echo "Running/Desired tasks: $ECS_STATUS"
if echo "$ECS_STATUS" | grep -q "1.*1"; then
    echo "✅ ECS service healthy"
else
    echo "⚠️  ECS service may be starting or unhealthy"
fi
echo ""

# Test 6: Check Lambda Functions
echo "Test 6: Lambda Functions"
echo "------------------------"
for func in feedback model evaluation; do
    STATUS=$(aws lambda get-function \
        --function-name ml-news-$func \
        --region $REGION \
        --query 'Configuration.State' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$STATUS" == "Active" ]; then
        echo "✅ ml-news-$func: Active"
    else
        echo "⚠️  ml-news-$func: $STATUS"
    fi
done
echo ""

# Test 7: Check RDS
echo "Test 7: RDS Database"
echo "--------------------"
RDS_STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier ml-news-db \
    --region $REGION \
    --query 'DBInstances[0].[DBInstanceStatus,Endpoint.Address]' \
    --output text)

echo "Status/Endpoint: $RDS_STATUS"
if echo "$RDS_STATUS" | grep -q "available"; then
    echo "✅ RDS database available"
else
    echo "⚠️  RDS database not fully available"
fi
echo ""

# Summary
echo "════════════════════════════════════════"
echo "📊 Test Summary"
echo "════════════════════════════════════════"
echo ""
echo "✅ = Working"
echo "⚠️  = Warning/Not Ready"
echo "❌ = Failed"
echo ""
echo "Next Steps:"
echo "1. If prediction API shows errors, train a model:"
echo "   curl -X POST $API_ENDPOINT/api/v1/model/train"
echo ""
echo "2. Monitor CloudWatch Logs:"
echo "   - /ecs/ml-news-inference"
echo "   - /aws/lambda/ml-news-*"
echo ""
echo "3. Check AWS Console for detailed status"
echo ""
