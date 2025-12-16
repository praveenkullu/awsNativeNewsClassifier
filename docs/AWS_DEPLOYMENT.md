# AWS Deployment Guide

## Overview

This guide covers deploying the ML News Categorization pipeline to AWS with cost optimization for low-traffic applications.

## Architecture Options

### Option 1: Serverless (Lowest Cost - Recommended for < 1000 requests/day)

**Estimated Cost: $5-20/month**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AWS Serverless Architecture                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────────────┐     │
│  │  Client  │────▶│ API Gateway  │────▶│    Lambda Functions      │     │
│  │          │◀────│   (HTTP)     │◀────│                          │     │
│  └──────────┘     └──────────────┘     │  - inference_handler     │     │
│                                         │  - feedback_handler      │     │
│                                         │  - model_handler         │     │
│                                         │  - evaluation_handler    │     │
│                                         └───────────┬──────────────┘     │
│                                                     │                    │
│                    ┌────────────────────────────────┼────────────────┐   │
│                    │                                │                │   │
│                    ▼                                ▼                ▼   │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌──────────────────┐     │
│  │     DynamoDB        │  │       S3        │  │   SageMaker      │     │
│  │  (Feedback, Meta)   │  │ (Models, Data)  │  │  (Training)      │     │
│  └─────────────────────┘  └─────────────────┘  └──────────────────┘     │
│                                                                          │
│  ┌─────────────────────┐                                                 │
│  │   CloudWatch        │  Logging, Metrics, Alarms                       │
│  └─────────────────────┘                                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Option 2: Container-Based (Low Cost - Recommended for 1000-10000 requests/day)

**Estimated Cost: $30-50/month**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       AWS ECS Fargate Architecture                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────────────┐     │
│  │  Client  │────▶│     ALB      │────▶│      ECS Fargate         │     │
│  │          │◀────│              │◀────│   (Spot Instances)       │     │
│  └──────────┘     └──────────────┘     │                          │     │
│                                         │  ┌────────────────────┐  │     │
│                                         │  │ api-gateway (1)    │  │     │
│                                         │  ├────────────────────┤  │     │
│                                         │  │ inference (1)      │  │     │
│                                         │  ├────────────────────┤  │     │
│                                         │  │ feedback (1)       │  │     │
│                                         │  ├────────────────────┤  │     │
│                                         │  │ model (0-1)*       │  │     │
│                                         │  ├────────────────────┤  │     │
│                                         │  │ evaluation (0-1)*  │  │     │
│                                         │  └────────────────────┘  │     │
│                                         └──────────────────────────┘     │
│                                         * Scaled to 0 when idle          │
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────┐  ┌──────────────────┐     │
│  │   RDS PostgreSQL    │  │       S3        │  │  ElastiCache     │     │
│  │    (db.t4g.micro)   │  │ (Models, Data)  │  │   (cache.t4g)    │     │
│  └─────────────────────┘  └─────────────────┘  └──────────────────┘     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Option 3: Single EC2 Instance (Simplest - Good for Development)

**Estimated Cost: $10-15/month**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       AWS EC2 Simple Architecture                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────┐                    ┌─────────────────────────────────┐    │
│  │  Client  │───────────────────▶│      EC2 t3.small               │    │
│  │          │◀───────────────────│      (Docker Compose)           │    │
│  └──────────┘                    │                                 │    │
│                                  │  ┌───────────────────────────┐  │    │
│                                  │  │    All Services           │  │    │
│                                  │  │    + PostgreSQL           │  │    │
│                                  │  │    + Redis                │  │    │
│                                  │  └───────────────────────────┘  │    │
│                                  └─────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────┐                                                 │
│  │         S3          │  (Model Storage - Optional)                     │
│  └─────────────────────┘                                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Option 1: Serverless Deployment (Recommended)

### Prerequisites

1. AWS CLI configured with appropriate permissions
2. AWS SAM CLI installed
3. Docker installed (for local testing)

### Step 1: Create S3 Buckets

```bash
# Create bucket for models
aws s3 mb s3://ml-news-models-${AWS_ACCOUNT_ID} --region us-east-1

# Create bucket for training data
aws s3 mb s3://ml-news-data-${AWS_ACCOUNT_ID} --region us-east-1

# Upload dataset
aws s3 cp data/News_Category_Dataset_v3.json \
    s3://ml-news-data-${AWS_ACCOUNT_ID}/raw/
```

### Step 2: Create DynamoDB Tables

```bash
# Feedback table
aws dynamodb create-table \
    --table-name ml-news-feedback \
    --attribute-definitions \
        AttributeName=prediction_id,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
    --key-schema \
        AttributeName=prediction_id,KeyType=HASH \
        AttributeName=created_at,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Model metadata table
aws dynamodb create-table \
    --table-name ml-news-models \
    --attribute-definitions \
        AttributeName=version,AttributeType=S \
    --key-schema \
        AttributeName=version,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Evaluation results table
aws dynamodb create-table \
    --table-name ml-news-evaluations \
    --attribute-definitions \
        AttributeName=evaluation_id,AttributeType=S \
    --key-schema \
        AttributeName=evaluation_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

### Step 3: Deploy Lambda Functions

Create the SAM template at `aws/template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: ML News Categorization Pipeline

Globals:
  Function:
    Timeout: 30
    MemorySize: 512
    Runtime: python3.10
    Environment:
      Variables:
        S3_MODEL_BUCKET: !Ref ModelBucket
        DYNAMODB_FEEDBACK_TABLE: !Ref FeedbackTable
        DYNAMODB_MODEL_TABLE: !Ref ModelTable

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Resources:
  # S3 Buckets
  ModelBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub ml-news-models-${AWS::AccountId}-${Environment}
      VersioningConfiguration:
        Status: Enabled

  # DynamoDB Tables
  FeedbackTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ml-news-feedback-${Environment}
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: prediction_id
          AttributeType: S
        - AttributeName: created_at
          AttributeType: S
      KeySchema:
        - AttributeName: prediction_id
          KeyType: HASH
        - AttributeName: created_at
          KeyType: RANGE

  ModelTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ml-news-models-${Environment}
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: version
          AttributeType: S
      KeySchema:
        - AttributeName: version
          KeyType: HASH

  # Lambda Functions
  InferenceFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ml-news-inference-${Environment}
      Handler: app.handler
      CodeUri: ../services/inference-service/
      MemorySize: 1024
      Timeout: 30
      Policies:
        - S3ReadPolicy:
            BucketName: !Ref ModelBucket
        - DynamoDBReadPolicy:
            TableName: !Ref ModelTable
      Events:
        Predict:
          Type: Api
          Properties:
            Path: /api/v1/predict
            Method: post
            RestApiId: !Ref ApiGateway
        PredictBatch:
          Type: Api
          Properties:
            Path: /api/v1/predict/batch
            Method: post
            RestApiId: !Ref ApiGateway

  FeedbackFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ml-news-feedback-${Environment}
      Handler: app.handler
      CodeUri: ../services/feedback-service/
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref FeedbackTable
      Events:
        SubmitFeedback:
          Type: Api
          Properties:
            Path: /api/v1/feedback
            Method: post
            RestApiId: !Ref ApiGateway
        GetStats:
          Type: Api
          Properties:
            Path: /api/v1/feedback/stats
            Method: get
            RestApiId: !Ref ApiGateway

  ModelFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ml-news-model-${Environment}
      Handler: app.handler
      CodeUri: ../services/model-service/
      MemorySize: 2048
      Timeout: 900
      Policies:
        - S3CrudPolicy:
            BucketName: !Ref ModelBucket
        - DynamoDBCrudPolicy:
            TableName: !Ref ModelTable
        - Statement:
            - Effect: Allow
              Action:
                - sagemaker:CreateTrainingJob
                - sagemaker:DescribeTrainingJob
              Resource: '*'
      Events:
        Train:
          Type: Api
          Properties:
            Path: /api/v1/model/train
            Method: post
            RestApiId: !Ref ApiGateway
        TrainStatus:
          Type: Api
          Properties:
            Path: /api/v1/model/train/{job_id}
            Method: get
            RestApiId: !Ref ApiGateway
        ListVersions:
          Type: Api
          Properties:
            Path: /api/v1/model/versions
            Method: get
            RestApiId: !Ref ApiGateway
        Deploy:
          Type: Api
          Properties:
            Path: /api/v1/model/deploy/{version}
            Method: post
            RestApiId: !Ref ApiGateway

  EvaluationFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ml-news-evaluation-${Environment}
      Handler: app.handler
      CodeUri: ../services/evaluation-service/
      MemorySize: 1024
      Timeout: 300
      Policies:
        - S3ReadPolicy:
            BucketName: !Ref ModelBucket
        - DynamoDBReadPolicy:
            TableName: !Ref FeedbackTable
        - DynamoDBCrudPolicy:
            TableName: !Ref ModelTable
      Events:
        Evaluate:
          Type: Api
          Properties:
            Path: /api/v1/model/evaluate
            Method: post
            RestApiId: !Ref ApiGateway
        EvaluationResult:
          Type: Api
          Properties:
            Path: /api/v1/model/evaluate/{evaluation_id}
            Method: get
            RestApiId: !Ref ApiGateway
        RetrainCheck:
          Type: Api
          Properties:
            Path: /api/v1/model/retrain-check
            Method: post
            RestApiId: !Ref ApiGateway

  # API Gateway
  ApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      Name: !Sub ml-news-api-${Environment}
      StageName: !Ref Environment
      Cors:
        AllowOrigin: "'*'"
        AllowMethods: "'GET,POST,OPTIONS'"
        AllowHeaders: "'Content-Type,X-Correlation-ID'"

  # Health check endpoint
  HealthFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ml-news-health-${Environment}
      Handler: app.handler
      InlineCode: |
        import json
        def handler(event, context):
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'healthy',
                    'service': 'ml-news-pipeline',
                    'version': '1.0.0'
                })
            }
      Events:
        Health:
          Type: Api
          Properties:
            Path: /health
            Method: get
            RestApiId: !Ref ApiGateway

Outputs:
  ApiEndpoint:
    Description: API Gateway endpoint URL
    Value: !Sub https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/${Environment}
  ModelBucketName:
    Description: S3 bucket for models
    Value: !Ref ModelBucket
```

### Step 4: Deploy with SAM

```bash
cd aws

# Build
sam build

# Deploy (first time - guided)
sam deploy --guided

# Subsequent deployments
sam deploy
```

### Step 5: Initial Model Training

```bash
# Upload training data
aws s3 cp data/News_Category_Dataset_v3.json \
    s3://${MODEL_BUCKET}/data/

# Trigger training via API
curl -X POST https://${API_ENDPOINT}/api/v1/model/train \
    -H "Content-Type: application/json" \
    -d '{"include_feedback": false}'
```

---

## Option 2: ECS Fargate Deployment

### Step 1: Create ECR Repositories

```bash
for service in api-gateway inference-service feedback-service model-service evaluation-service; do
    aws ecr create-repository \
        --repository-name ml-news/${service} \
        --region us-east-1
done
```

### Step 2: Build and Push Docker Images

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Build and push each service
for service in api-gateway inference-service feedback-service model-service evaluation-service; do
    docker build -t ml-news/${service} services/${service}/
    docker tag ml-news/${service}:latest \
        ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/ml-news/${service}:latest
    docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/ml-news/${service}:latest
done
```

### Step 3: Create ECS Task Definitions

Create `aws/ecs-task-def-inference.json`:

```json
{
  "family": "ml-news-inference",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "inference-service",
      "image": "${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/ml-news/inference-service:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8001,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "S3_MODEL_BUCKET", "value": "ml-news-models"},
        {"name": "REDIS_HOST", "value": "ml-news-redis.xxxxx.cache.amazonaws.com"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ml-news-inference",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8001/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

### Step 4: Create ECS Service with Spot Capacity

```bash
# Create cluster
aws ecs create-cluster --cluster-name ml-news-cluster

# Create service with Fargate Spot (70% cost savings)
aws ecs create-service \
    --cluster ml-news-cluster \
    --service-name inference-service \
    --task-definition ml-news-inference \
    --desired-count 1 \
    --launch-type FARGATE \
    --capacity-provider-strategy \
        capacityProvider=FARGATE_SPOT,weight=1 \
    --network-configuration \
        "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### Step 5: Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
    --name ml-news-alb \
    --subnets subnet-xxx subnet-yyy \
    --security-groups sg-xxx

# Create target groups for each service
aws elbv2 create-target-group \
    --name ml-news-inference-tg \
    --protocol HTTP \
    --port 8001 \
    --vpc-id vpc-xxx \
    --target-type ip \
    --health-check-path /health
```

---

## Option 3: EC2 Single Instance Deployment

### Step 1: Launch EC2 Instance

```bash
# Launch t3.small instance (cost-effective)
aws ec2 run-instances \
    --image-id ami-0c7217cdde317cfec \
    --instance-type t3.small \
    --key-name your-key-pair \
    --security-group-ids sg-xxx \
    --subnet-id subnet-xxx \
    --iam-instance-profile Name=ec2-s3-role \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ml-news-server}]' \
    --user-data file://scripts/ec2-userdata.sh
```

### Step 2: EC2 User Data Script

Create `scripts/ec2-userdata.sh`:

```bash
#!/bin/bash
set -e

# Update system
yum update -y

# Install Docker
amazon-linux-extras install docker -y
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Git
yum install git -y

# Clone repository
cd /home/ec2-user
git clone https://github.com/your-repo/ml-news-categorization.git
cd ml-news-categorization

# Create environment file
cat > .env << 'EOF'
POSTGRES_USER=mlnews
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=mlnews
REDIS_HOST=redis
AWS_REGION=us-east-1
S3_BUCKET=ml-news-models
EOF

# Start services
docker-compose up -d

# Configure auto-restart on reboot
cat > /etc/systemd/system/ml-news.service << 'EOF'
[Unit]
Description=ML News Categorization
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ec2-user/ml-news-categorization
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down

[Install]
WantedBy=multi-user.target
EOF

systemctl enable ml-news.service
```

### Step 3: Configure Security Group

```bash
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxx \
    --protocol tcp \
    --port 8000 \
    --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
    --group-id sg-xxx \
    --protocol tcp \
    --port 22 \
    --cidr YOUR_IP/32
```

---

## Model Training with SageMaker (Optional)

For more complex training needs, use SageMaker:

### Create SageMaker Training Job

```python
import boto3
import sagemaker
from sagemaker.sklearn import SKLearn

session = sagemaker.Session()
role = 'arn:aws:iam::${ACCOUNT_ID}:role/SageMakerRole'

sklearn_estimator = SKLearn(
    entry_point='train.py',
    source_dir='model/',
    role=role,
    instance_count=1,
    instance_type='ml.m5.large',  # Use Spot for 70% savings
    use_spot_instances=True,
    max_wait=3600,
    framework_version='1.0-1',
    py_version='py3',
    hyperparameters={
        'epochs': 10,
        'batch_size': 32
    }
)

# Start training
sklearn_estimator.fit({
    'train': 's3://ml-news-data/train/',
    'test': 's3://ml-news-data/test/'
})
```

---

## Cost Optimization Tips

### 1. Use AWS Free Tier
- Lambda: 1M free requests/month
- DynamoDB: 25 GB free storage
- S3: 5 GB free storage
- API Gateway: 1M free API calls/month

### 2. Implement Caching
```python
# Use ElastiCache or Lambda response caching
import functools

@functools.lru_cache(maxsize=1000)
def get_prediction(headline_hash):
    # Cached predictions
    pass
```

### 3. Use Spot Instances
- ECS Fargate Spot: 70% savings
- SageMaker Spot: 70% savings on training

### 4. Right-size Resources
- Start with minimum resources
- Use CloudWatch to monitor and adjust

### 5. Enable Auto-scaling to Zero
```yaml
# ECS Service Auto Scaling
ScalableTarget:
  Type: AWS::ApplicationAutoScaling::ScalableTarget
  Properties:
    MinCapacity: 0  # Scale to zero when idle
    MaxCapacity: 2
    ResourceId: !Sub service/${ECSCluster}/${ECSService.Name}
    ScalableDimension: ecs:service:DesiredCount
    ServiceNamespace: ecs
```

---

## Monitoring and Alerting

### CloudWatch Alarms

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
    --alarm-name ml-news-high-errors \
    --alarm-description "High error rate detected" \
    --metric-name 5XXError \
    --namespace AWS/ApiGateway \
    --statistic Sum \
    --period 300 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2

# Model accuracy alarm
aws cloudwatch put-metric-alarm \
    --alarm-name ml-news-low-accuracy \
    --alarm-description "Model accuracy below threshold" \
    --metric-name ModelAccuracy \
    --namespace MLNews \
    --statistic Average \
    --period 3600 \
    --threshold 0.75 \
    --comparison-operator LessThanThreshold
```

### X-Ray Tracing

Enable distributed tracing for debugging:

```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()

@xray_recorder.capture('predict')
def predict(text):
    # Your prediction logic
    pass
```

---

## Security Best Practices

1. **Use IAM Roles** - Never use access keys in code
2. **Enable VPC** - Run services in private subnets
3. **Encrypt Data** - Enable S3 encryption and DynamoDB encryption
4. **API Authentication** - Use API Gateway API keys or Cognito
5. **Secrets Management** - Use AWS Secrets Manager

```bash
# Store secrets
aws secretsmanager create-secret \
    --name ml-news/database \
    --secret-string '{"username":"mlnews","password":"secure_password"}'
```

---

## Terraform Alternative

For Infrastructure as Code, see `aws/terraform/` directory for Terraform configurations.

```bash
cd aws/terraform
terraform init
terraform plan
terraform apply
```
