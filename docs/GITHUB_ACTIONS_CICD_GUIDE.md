# GitHub Actions CI/CD Guide for ML News Categorization

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [AWS Configuration](#aws-configuration)
5. [GitHub Secrets Setup](#github-secrets-setup)
6. [Workflow Files](#workflow-files)
7. [Deployment Process](#deployment-process)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

This guide sets up a complete CI/CD pipeline using GitHub Actions for the ML News Categorization application with the following capabilities:

- **Automated Testing**: Run tests on every push and pull request
- **Lambda Deployment**: Build and deploy Lambda functions (feedback, model, evaluation services)
- **ECS Deployment**: Build Docker images and deploy to ECS Fargate (inference service)
- **Web Interface**: Deploy static files to S3
- **Multi-Environment**: Support for dev, staging, and production
- **Rollback**: Automated rollback capabilities

### Architecture Components
- **ECS Fargate**: Inference service (Docker container)
- **Lambda**: Feedback, Model, and Evaluation services
- **S3**: Static web interface hosting
- **ECR**: Docker image registry
- **API Gateway**: HTTP API routing
- **RDS**: PostgreSQL database

---

## Prerequisites

### 1. AWS Account Setup
- AWS Account with appropriate permissions
- AWS CLI configured locally
- Access to create IAM roles and policies

### 2. GitHub Repository
- GitHub repository with the ML News Categorization code
- Admin access to configure secrets and workflows
- Branch protection rules configured (recommended)

### 3. Required AWS Resources
Ensure these resources exist:
- ECR Repository: `ml-news-inference`
- ECS Cluster: `ml-news-cluster`
- ECS Service: `ml-news-inference-service`
- Lambda Functions: `ml-news-feedback`, `ml-news-model`, `ml-news-evaluation`
- S3 Bucket: `ml-news-web-interface-{account-id}`

---

## Quick Start

### Step 1: Create GitHub Actions Workflow Directory

```bash
mkdir -p .github/workflows
```

### Step 2: Create AWS IAM Role for GitHub Actions

```bash
# Set your AWS account ID
AWS_ACCOUNT_ID="289140051471"
GITHUB_ORG="your-github-username"
GITHUB_REPO="temp_tincsi_pf_news_2"

# Create trust policy for GitHub OIDC
cat > github-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${GITHUB_REPO}:*"
        }
      }
    }
  ]
}
EOF

# Create the IAM role
aws iam create-role \
  --role-name GitHubActionsMLNewsRole \
  --assume-role-policy-document file://github-trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name GitHubActionsMLNewsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
  --role-name GitHubActionsMLNewsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess

# Create custom policy for Lambda and S3
cat > github-actions-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:PublishVersion",
        "lambda:UpdateAlias",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:ListVersionsByFunction",
        "lambda:GetAlias"
      ],
      "Resource": [
        "arn:aws:lambda:us-east-2:${AWS_ACCOUNT_ID}:function:ml-news-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::ml-news-web-interface-${AWS_ACCOUNT_ID}",
        "arn:aws:s3:::ml-news-web-interface-${AWS_ACCOUNT_ID}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name GitHubActionsMLNewsPolicy \
  --policy-document file://github-actions-policy.json

aws iam attach-role-policy \
  --role-name GitHubActionsMLNewsRole \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/GitHubActionsMLNewsPolicy
```

### Step 3: Configure GitHub OIDC Provider (if not exists)

```bash
# Check if OIDC provider exists
aws iam list-open-id-connect-providers | grep token.actions.githubusercontent.com

# If not exists, create it
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### Step 4: Add GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

| Secret Name | Value | Description |
|------------|-------|-------------|
| `AWS_ACCOUNT_ID` | `289140051471` | Your AWS account ID |
| `AWS_REGION` | `us-east-2` | AWS region |
| `AWS_ROLE_ARN` | `arn:aws:iam::289140051471:role/GitHubActionsMLNewsRole` | IAM role ARN created above |
| `ECR_REPOSITORY` | `ml-news-inference` | ECR repository name |
| `ECS_CLUSTER` | `ml-news-cluster` | ECS cluster name |
| `ECS_SERVICE` | `ml-news-inference-service` | ECS service name |
| `S3_WEB_BUCKET` | `ml-news-web-interface-289140051471` | S3 bucket for web interface |
| `API_GATEWAY_URL` | `https://w6of479oic.execute-api.us-east-2.amazonaws.com` | API Gateway URL |

---

## AWS Configuration

### Lambda Function Names
Ensure your Lambda functions follow the naming convention:
- `ml-news-feedback`
- `ml-news-model`
- `ml-news-evaluation`

### ECS Task Definition
Your task definition should be named: `ml-news-inference`

### ECR Repository
Repository name: `ml-news-inference`

---

## GitHub Secrets Setup

### Required Secrets

```bash
# Navigate to GitHub repo
# Settings → Secrets and variables → Actions → New repository secret

# Add each secret:
AWS_ACCOUNT_ID=289140051471
AWS_REGION=us-east-2
AWS_ROLE_ARN=arn:aws:iam::289140051471:role/GitHubActionsMLNewsRole
ECR_REPOSITORY=ml-news-inference
ECS_CLUSTER=ml-news-cluster
ECS_SERVICE=ml-news-inference-service
ECS_TASK_DEFINITION=ml-news-inference
S3_WEB_BUCKET=ml-news-web-interface-289140051471
API_GATEWAY_URL=https://w6of479oic.execute-api.us-east-2.amazonaws.com
```

### Optional Secrets (for advanced features)

```bash
# Slack notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Database credentials (if needed for migrations)
DATABASE_URL=postgresql://mlnews:password@endpoint:5432/mlnews

# SageMaker role
SAGEMAKER_ROLE_ARN=arn:aws:iam::289140051471:role/ml-news-sagemaker-role
```

---

## Workflow Files

### Main Deployment Workflow

Create `.github/workflows/deploy.yml`:

This workflow handles:
- Running tests
- Building Lambda packages
- Building and pushing Docker images to ECR
- Deploying to AWS

### Web Interface Deployment

Create `.github/workflows/deploy-web.yml`:

This workflow:
- Deploys static files to S3
- Updates API Gateway URL in JavaScript
- Invalidates CloudFront cache (if applicable)

### Manual Training Trigger

Create `.github/workflows/trigger-training.yml`:

This workflow:
- Manually triggers SageMaker training jobs
- Monitors training progress
- Updates model versions

---

## Deployment Process

### Automated Deployment (Push to Main)

```bash
# 1. Create a feature branch
git checkout -b feature/my-feature

# 2. Make changes and commit
git add .
git commit -m "feat: add new feature"

# 3. Push to GitHub
git push origin feature/my-feature

# 4. Create Pull Request
# - Tests will run automatically
# - Review and merge to main

# 5. After merge to main
# - Workflow automatically deploys to AWS
# - Lambda functions updated
# - ECS service updated with new image
# - Web interface deployed to S3
```

### Manual Deployment

```bash
# Go to GitHub Actions → Deploy ML News Services → Run workflow
# Select branch and environment
```

### Deployment Flow

```
┌─────────────────┐
│  Push to Main   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Run Tests     │
│  - Unit Tests   │
│  - Integration  │
│  - Lint         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Build Packages  │
│  - Lambda ZIPs  │
│  - Docker Image │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Deploy to AWS   │
│  - Lambda Fns   │
│  - ECS Service  │
│  - S3 Static    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Smoke Tests    │
│  - Health Check │
│  - API Tests    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   ✅ Success    │
└─────────────────┘
```

---

## Best Practices

### 1. Branch Strategy

```
main        → Production
  └─ develop   → Development/Staging
       └─ feature/* → Feature branches
```

### 2. Environment Variables

Use GitHub Environments for different deployment stages:
- `dev` - Development environment
- `staging` - Staging/QA environment
- `production` - Production environment (requires approval)

### 3. Testing Strategy

```yaml
# Run tests on every push
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
```

### 4. Deployment Approval

For production deployments, require manual approval:

```yaml
environment:
  name: production
  url: https://api.ml-news.example.com
```

Configure approval in: Repository → Settings → Environments → production → Required reviewers

### 5. Rollback Strategy

Keep previous Lambda versions:

```bash
# Automatic versioning with aliases
aws lambda publish-version --function-name ml-news-feedback
aws lambda update-alias --function-name ml-news-feedback \
  --name live --function-version $VERSION
```

For ECS, keep previous task definition revisions:

```bash
# Rollback to previous task definition
aws ecs update-service --cluster ml-news-cluster \
  --service ml-news-inference-service \
  --task-definition ml-news-inference:PREVIOUS_REVISION
```

### 6. Monitoring and Notifications

Add Slack notifications to workflows:

```yaml
- name: Notify Slack
  if: always()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "Deployment ${{ job.status }}: ${{ github.repository }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Deployment Status*: ${{ job.status }}\n*Repository*: ${{ github.repository }}\n*Branch*: ${{ github.ref }}"
            }
          }
        ]
      }
```

### 7. Cost Optimization

- Use caching for dependencies
- Use matrix builds for parallel execution
- Clean up old artifacts
- Use spot instances for ECS where possible

### 8. Security Best Practices

- ✅ Use OIDC for AWS authentication (no long-lived credentials)
- ✅ Least privilege IAM policies
- ✅ Encrypt secrets at rest
- ✅ Enable branch protection rules
- ✅ Require pull request reviews
- ✅ Run security scanning (Dependabot, CodeQL)

---

## Troubleshooting

### Issue 1: AWS Authentication Failed

**Error**: `Unable to assume role`

**Solution**:
1. Verify OIDC provider is configured:
   ```bash
   aws iam list-open-id-connect-providers
   ```
2. Check IAM role trust policy includes GitHub repo
3. Verify `AWS_ROLE_ARN` secret is correct

### Issue 2: Lambda Deployment Failed

**Error**: `ResourceConflictException: The operation cannot be performed at this time`

**Solution**:
Wait for previous update to complete:
```bash
aws lambda wait function-updated \
  --function-name ml-news-feedback
```

### Issue 3: ECS Deployment Timeout

**Error**: `Service did not stabilize`

**Solution**:
1. Check ECS task logs in CloudWatch
2. Verify Docker image is valid
3. Check task definition has correct environment variables
4. Increase timeout in workflow:
   ```yaml
   timeout-minutes: 15
   ```

### Issue 4: Docker Build Failed

**Error**: `No space left on device`

**Solution**:
```yaml
- name: Clean up Docker
  run: docker system prune -af
```

### Issue 5: Lambda Package Too Large

**Error**: `RequestEntityTooLargeException`

**Solution**:
1. Use Docker-based Lambda build (already implemented)
2. Remove unnecessary dependencies
3. Use Lambda Layers for common dependencies

### Issue 6: S3 Deployment Failed

**Error**: `AccessDenied`

**Solution**:
Verify S3 bucket policy allows PutObject:
```bash
aws s3api get-bucket-policy --bucket ml-news-web-interface-289140051471
```

---

## Workflow Examples

### Example 1: Simple Deployment Workflow

Deploys on every push to main:

```yaml
name: Deploy to AWS
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        run: echo "Deploying..."
```

### Example 2: Multi-Environment Workflow

Deploys to different environments based on branch:

```yaml
name: Multi-Environment Deploy
on:
  push:
    branches: [main, develop]
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: ${{ github.ref == 'refs/heads/main' && 'production' || 'development' }}
```

### Example 3: Manual Trigger with Parameters

Allows manual deployment with environment selection:

```yaml
name: Manual Deploy
on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment'
        required: true
        type: choice
        options:
          - dev
          - staging
          - production
```

---

## Next Steps

1. ✅ Create `.github/workflows` directory
2. ✅ Add workflow files (provided in next section)
3. ✅ Configure GitHub secrets
4. ✅ Create AWS IAM role for GitHub Actions
5. ✅ Test deployment with a small change
6. ✅ Set up branch protection rules
7. ✅ Configure environment approvals
8. ✅ Add monitoring and notifications

---

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS Actions on GitHub Marketplace](https://github.com/marketplace?type=actions&query=aws)
- [OIDC with GitHub Actions](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [ECS Deploy Task Definition](https://github.com/aws-actions/amazon-ecs-deploy-task-definition)
- [ECR Login Action](https://github.com/aws-actions/amazon-ecr-login)
