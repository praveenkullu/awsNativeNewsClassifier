#!/bin/bash
set -e

# Complete ECS Deployment Script
# This script completes the ECS setup: target group, task definition, and service

REGION="us-east-2"
CLUSTER_NAME="ml-news-cluster"
ALB_ARN="arn:aws:elasticloadbalancing:us-east-2:289140051471:loadbalancer/app/ml-news-alb/3e1f48a1aefeef4d"
VPC_ID="vpc-064df0da6b472dcae"
PUB_SUBNET_1="subnet-066053b3fa2a3b863"
PUB_SUBNET_2="subnet-07e66e013e6ec43c4"
ECS_SG="sg-05df6c17bc1a67d66"
ECR_IMAGE="289140051471.dkr.ecr.us-east-2.amazonaws.com/ml-news/inference-service:latest"
TASK_EXECUTION_ROLE="arn:aws:iam::289140051471:role/ml-news-ecs-task-execution-role"
TASK_ROLE="arn:aws:iam::289140051471:role/ml-news-ecs-task-role"

echo "🚀 Completing ECS Deployment"
echo "=============================="

# Step 1: Get RDS endpoint (wait if not ready)
echo "📊 Step 1: Getting RDS endpoint..."
RDS_ENDPOINT=""
while [ -z "$RDS_ENDPOINT" ]; do
    RDS_STATUS=$(aws rds describe-db-instances \
        --db-instance-identifier ml-news-db \
        --region $REGION \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text)

    if [ "$RDS_STATUS" == "available" ]; then
        RDS_ENDPOINT=$(aws rds describe-db-instances \
            --db-instance-identifier ml-news-db \
            --region $REGION \
            --query 'DBInstances[0].Endpoint.Address' \
            --output text)
        echo "✅ RDS is available: $RDS_ENDPOINT"
    else
        echo "⏳ RDS status: $RDS_STATUS - waiting 30 seconds..."
        sleep 30
    fi
done

# Step 2: Create Target Group
echo ""
echo "🎯 Step 2: Creating ALB target group..."
TG_ARN=$(aws elbv2 create-target-group \
    --name ml-news-inference-tg \
    --protocol HTTP \
    --port 8001 \
    --vpc-id $VPC_ID \
    --target-type ip \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --region $REGION \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)

echo "✅ Target group created: $TG_ARN"

# Step 3: Create ALB Listener
echo ""
echo "🔊 Step 3: Creating ALB listener..."
LISTENER_ARN=$(aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN \
    --region $REGION \
    --query 'Listeners[0].ListenerArn' \
    --output text)

echo "✅ Listener created: $LISTENER_ARN"

# Step 4: Create ECS Task Definition
echo ""
echo "📋 Step 4: Creating ECS task definition..."
cat > /tmp/task-definition.json <<EOF
{
  "family": "ml-news-inference",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "$TASK_EXECUTION_ROLE",
  "taskRoleArn": "$TASK_ROLE",
  "containerDefinitions": [
    {
      "name": "inference-service",
      "image": "$ECR_IMAGE",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8001,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "MODEL_PATH",
          "value": "/app/models/default/model.pkl"
        },
        {
          "name": "MODEL_SERVICE_URL",
          "value": "http://localhost:8003"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        },
        {
          "name": "PYTHONPATH",
          "value": "/app:/app/model"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ml-news-inference",
          "awslogs-region": "$REGION",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8001/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF

TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json file:///tmp/task-definition.json \
    --region $REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "✅ Task definition registered: $TASK_DEF_ARN"

# Step 5: Create ECS Service
echo ""
echo "🔧 Step 5: Creating ECS service..."
aws ecs create-service \
    --cluster $CLUSTER_NAME \
    --service-name ml-news-inference-service \
    --task-definition ml-news-inference \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$PUB_SUBNET_1,$PUB_SUBNET_2],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=inference-service,containerPort=8001" \
    --region $REGION > /dev/null

echo "✅ ECS service created"

# Step 6: Wait for service to stabilize
echo ""
echo "⏳ Step 6: Waiting for service to become stable (this may take 2-3 minutes)..."
aws ecs wait services-stable \
    --cluster $CLUSTER_NAME \
    --services ml-news-inference-service \
    --region $REGION

echo "✅ ECS service is stable"

# Step 7: Test the deployment
echo ""
echo "🧪 Step 7: Testing deployment..."
ALB_DNS=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns $ALB_ARN \
    --region $REGION \
    --query 'LoadBalancers[0].DNSName' \
    --output text)

echo "Waiting 10 seconds for ALB to update..."
sleep 10

if curl -f -s "http://$ALB_DNS/health" > /dev/null; then
    echo "✅ Health check passed!"
else
    echo "⚠️  Health check failed - service may still be starting"
fi

# Summary
echo ""
echo "════════════════════════════════════════"
echo "✅ ECS Deployment Complete!"
echo "════════════════════════════════════════"
echo ""
echo "Resources created:"
echo "  - Target Group: $TG_ARN"
echo "  - Listener: $LISTENER_ARN"
echo "  - Task Definition: ml-news-inference"
echo "  - ECS Service: ml-news-inference-service"
echo ""
echo "Access your service:"
echo "  Health: http://$ALB_DNS/health"
echo "  Predict: http://$ALB_DNS/api/v1/predict"
echo ""
echo "Next steps:"
echo "  1. Run: ./scripts/deploy-lambda-functions.sh"
echo "  2. Run: ./scripts/setup-api-gateway.sh"
echo "  3. Run: ./scripts/upload-training-data.sh"
echo ""
