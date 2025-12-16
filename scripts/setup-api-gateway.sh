#!/bin/bash
set -e

# Setup API Gateway Script
# Creates HTTP API Gateway and integrates with Lambda functions and ALB

REGION="us-east-2"
ALB_DNS="ml-news-alb-144180680.us-east-2.elb.amazonaws.com"
ALB_ARN="arn:aws:elasticloadbalancing:us-east-2:289140051471:loadbalancer/app/ml-news-alb/3e1f48a1aefeef4d"
LISTENER_ARN=$(aws elbv2 describe-listeners --load-balancer-arn $ALB_ARN --region $REGION --query 'Listeners[0].ListenerArn' --output text)

echo "🌐 Setting up API Gateway"
echo "========================="

# Create HTTP API
echo "Creating HTTP API..."
API_ID=$(aws apigatewayv2 create-api \
    --name ml-news-api \
    --protocol-type HTTP \
    --description "ML News Categorization API" \
    --region $REGION \
    --query 'ApiId' \
    --output text)

echo "✅ API created: $API_ID"

# Create VPC Link for ALB integration
echo ""
echo "Creating VPC Link for ALB..."
VPC_LINK_ID=$(aws apigatewayv2 create-vpc-link \
    --name ml-news-vpc-link \
    --subnet-ids subnet-066053b3fa2a3b863 subnet-07e66e013e6ec43c4 \
    --security-group-ids sg-05df6c17bc1a67d66 \
    --region $REGION \
    --query 'VpcLinkId' \
    --output text)

echo "✅ VPC Link created: $VPC_LINK_ID"
echo "⏳ Waiting for VPC Link to become available..."

# Wait for VPC Link to be available
while true; do
    STATUS=$(aws apigatewayv2 get-vpc-link --vpc-link-id $VPC_LINK_ID --region $REGION --query 'VpcLinkStatus' --output text)
    if [ "$STATUS" == "AVAILABLE" ]; then
        echo "✅ VPC Link is available"
        break
    fi
    echo "   Status: $STATUS - waiting..."
    sleep 10
done

# Create integration for inference service (via ALB)
echo ""
echo "Creating ALB integration..."
INFERENCE_INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id $API_ID \
    --integration-type HTTP_PROXY \
    --integration-method ANY \
    --integration-uri $LISTENER_ARN \
    --connection-type VPC_LINK \
    --connection-id $VPC_LINK_ID \
    --payload-format-version 1.0 \
    --region $REGION \
    --query 'IntegrationId' \
    --output text)

echo "✅ ALB integration created"

# Create Lambda integrations
echo ""
echo "Creating Lambda integrations..."

for func in feedback model evaluation; do
    FUNCTION_ARN="arn:aws:lambda:$REGION:289140051471:function:ml-news-$func"

    # Grant API Gateway permission to invoke Lambda
    aws lambda add-permission \
        --function-name ml-news-$func \
        --statement-id apigateway-invoke-$func \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:$REGION:289140051471:$API_ID/*/*" \
        --region $REGION 2>/dev/null || echo "  Permission already exists for $func"

    # Create integration
    INTEGRATION_ID=$(aws apigatewayv2 create-integration \
        --api-id $API_ID \
        --integration-type AWS_PROXY \
        --integration-uri $FUNCTION_ARN \
        --payload-format-version 2.0 \
        --region $REGION \
        --query 'IntegrationId' \
        --output text)

    echo "✅ Lambda integration for $func: $INTEGRATION_ID"

    # Store for route creation
    eval "${func}_INTEGRATION_ID=$INTEGRATION_ID"
done

# Create routes
echo ""
echo "Creating API routes..."

# Inference routes (via ALB)
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'POST /api/v1/predict' \
    --target "integrations/$INFERENCE_INTEGRATION_ID" \
    --region $REGION > /dev/null
echo "✅ Route: POST /api/v1/predict → Inference Service"

aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'GET /health' \
    --target "integrations/$INFERENCE_INTEGRATION_ID" \
    --region $REGION > /dev/null
echo "✅ Route: GET /health → Inference Service"

# Feedback routes (Lambda)
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'POST /api/v1/feedback' \
    --target "integrations/$feedback_INTEGRATION_ID" \
    --region $REGION > /dev/null
echo "✅ Route: POST /api/v1/feedback → Feedback Lambda"

# Model service routes (Lambda)
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'POST /api/v1/model/train' \
    --target "integrations/$model_INTEGRATION_ID" \
    --region $REGION > /dev/null
echo "✅ Route: POST /api/v1/model/train → Model Lambda"

aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'GET /api/v1/model/versions' \
    --target "integrations/$model_INTEGRATION_ID" \
    --region $REGION > /dev/null
echo "✅ Route: GET /api/v1/model/versions → Model Lambda"

# Evaluation routes (Lambda)
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'POST /api/v1/model/evaluate' \
    --target "integrations/$evaluation_INTEGRATION_ID" \
    --region $REGION > /dev/null
echo "✅ Route: POST /api/v1/model/evaluate → Evaluation Lambda"

# Create default stage
echo ""
echo "Creating default stage..."
aws apigatewayv2 create-stage \
    --api-id $API_ID \
    --stage-name '$default' \
    --auto-deploy \
    --region $REGION > /dev/null

API_ENDPOINT=$(aws apigatewayv2 get-api --api-id $API_ID --region $REGION --query 'ApiEndpoint' --output text)

echo ""
echo "════════════════════════════════════════"
echo "✅ API Gateway Setup Complete!"
echo "════════════════════════════════════════"
echo ""
echo "API Endpoint: $API_ENDPOINT"
echo ""
echo "Available routes:"
echo "  POST $API_ENDPOINT/api/v1/predict"
echo "  POST $API_ENDPOINT/api/v1/feedback"
echo "  POST $API_ENDPOINT/api/v1/model/train"
echo "  GET  $API_ENDPOINT/api/v1/model/versions"
echo "  POST $API_ENDPOINT/api/v1/model/evaluate"
echo "  GET  $API_ENDPOINT/health"
echo ""
echo "Test with:"
echo "  curl $API_ENDPOINT/health"
echo ""
