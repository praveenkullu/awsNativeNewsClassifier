#!/bin/bash
#
# GitHub Actions Setup Script for ML News Categorization
# This script automates the setup of GitHub Actions CI/CD pipeline
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-289140051471}"
AWS_REGION="${AWS_REGION:-us-east-2}"
GITHUB_ORG="${GITHUB_ORG:-}"
GITHUB_REPO="${GITHUB_REPO:-temp_tincsi_pf_news_2}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   GitHub Actions Setup for ML News Categorization         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print step
print_step() {
    echo -e "${GREEN}==>${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Check prerequisites
print_step "Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    print_warning "jq is not installed. Some features may not work."
fi

if ! command -v gh &> /dev/null; then
    print_warning "GitHub CLI (gh) is not installed. You'll need to configure secrets manually."
fi

print_success "Prerequisites check completed"
echo ""

# Get GitHub organization/username
if [ -z "$GITHUB_ORG" ]; then
    echo -e "${BLUE}Enter your GitHub username or organization:${NC}"
    read -r GITHUB_ORG
fi

# Confirm configuration
print_step "Configuration:"
echo "  AWS Account ID: $AWS_ACCOUNT_ID"
echo "  AWS Region: $AWS_REGION"
echo "  GitHub Org/User: $GITHUB_ORG"
echo "  GitHub Repo: $GITHUB_REPO"
echo ""

read -p "Is this correct? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_error "Setup cancelled"
    exit 1
fi

# Step 1: Check if OIDC provider exists
print_step "Step 1: Checking GitHub OIDC provider..."

OIDC_EXISTS=$(aws iam list-open-id-connect-providers --output text | grep -c "token.actions.githubusercontent.com" || true)

if [ "$OIDC_EXISTS" -eq 0 ]; then
    print_warning "GitHub OIDC provider not found. Creating..."

    aws iam create-open-id-connect-provider \
        --url https://token.actions.githubusercontent.com \
        --client-id-list sts.amazonaws.com \
        --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

    print_success "OIDC provider created"
else
    print_success "OIDC provider already exists"
fi

# Step 2: Create IAM role for GitHub Actions
print_step "Step 2: Creating IAM role for GitHub Actions..."

ROLE_NAME="GitHubActionsMLNewsRole"

# Create trust policy
cat > /tmp/github-trust-policy.json <<EOF
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

# Check if role exists
if aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
    print_warning "Role already exists. Updating trust policy..."
    aws iam update-assume-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-document file:///tmp/github-trust-policy.json
else
    print_warning "Creating new role..."
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/github-trust-policy.json \
        --description "Role for GitHub Actions to deploy ML News Categorization"
fi

print_success "IAM role configured"

# Step 3: Attach policies
print_step "Step 3: Attaching IAM policies..."

# Attach AWS managed policies
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser \
    2>/dev/null || true

aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess \
    2>/dev/null || true

# Create custom policy
POLICY_NAME="GitHubActionsMLNewsPolicy"

cat > /tmp/github-actions-policy.json <<EOF
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
        "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:ml-news-*"
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

# Check if policy exists
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"
if aws iam get-policy --policy-arn "$POLICY_ARN" &> /dev/null; then
    print_warning "Policy already exists. Creating new version..."

    # Get default version
    DEFAULT_VERSION=$(aws iam get-policy --policy-arn "$POLICY_ARN" --query 'Policy.DefaultVersionId' --output text)

    # Create new version
    NEW_VERSION=$(aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file:///tmp/github-actions-policy.json \
        --set-as-default \
        --query 'PolicyVersion.VersionId' \
        --output text)

    # Delete old version
    aws iam delete-policy-version \
        --policy-arn "$POLICY_ARN" \
        --version-id "$DEFAULT_VERSION" || true
else
    print_warning "Creating new policy..."
    POLICY_ARN=$(aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///tmp/github-actions-policy.json \
        --query 'Policy.Arn' \
        --output text)
fi

# Attach custom policy
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "$POLICY_ARN" \
    2>/dev/null || true

print_success "Policies attached"

# Step 4: Get role ARN
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
print_success "Role ARN: $ROLE_ARN"
echo ""

# Step 5: Get API Gateway URL
print_step "Step 4: Getting API Gateway URL..."

API_ID=$(aws apigatewayv2 get-apis --region "$AWS_REGION" --query "Items[?Name=='ml-news-api'].ApiId" --output text)

if [ -n "$API_ID" ]; then
    API_GATEWAY_URL="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com"
    print_success "API Gateway URL: $API_GATEWAY_URL"
else
    print_warning "API Gateway not found. You'll need to set this manually."
    API_GATEWAY_URL="https://YOUR_API_ID.execute-api.${AWS_REGION}.amazonaws.com"
fi

# Step 6: Configure GitHub secrets
print_step "Step 5: Configuring GitHub secrets..."

if command -v gh &> /dev/null; then
    print_warning "Setting GitHub secrets using gh CLI..."

    gh secret set AWS_ACCOUNT_ID --body "$AWS_ACCOUNT_ID" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
    gh secret set AWS_REGION --body "$AWS_REGION" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
    gh secret set AWS_ROLE_ARN --body "$ROLE_ARN" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
    gh secret set ECR_REPOSITORY --body "ml-news-inference" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
    gh secret set ECS_CLUSTER --body "ml-news-cluster" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
    gh secret set ECS_SERVICE --body "ml-news-inference-service" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
    gh secret set S3_WEB_BUCKET --body "ml-news-web-interface-${AWS_ACCOUNT_ID}" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
    gh secret set API_GATEWAY_URL --body "$API_GATEWAY_URL" --repo "${GITHUB_ORG}/${GITHUB_REPO}"

    print_success "GitHub secrets configured"
else
    print_warning "GitHub CLI not found. Please configure secrets manually:"
    echo ""
    echo "Go to: https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/settings/secrets/actions"
    echo ""
    echo "Add the following secrets:"
    echo "  AWS_ACCOUNT_ID = $AWS_ACCOUNT_ID"
    echo "  AWS_REGION = $AWS_REGION"
    echo "  AWS_ROLE_ARN = $ROLE_ARN"
    echo "  ECR_REPOSITORY = ml-news-inference"
    echo "  ECS_CLUSTER = ml-news-cluster"
    echo "  ECS_SERVICE = ml-news-inference-service"
    echo "  S3_WEB_BUCKET = ml-news-web-interface-${AWS_ACCOUNT_ID}"
    echo "  API_GATEWAY_URL = $API_GATEWAY_URL"
    echo ""
fi

# Cleanup
rm -f /tmp/github-trust-policy.json
rm -f /tmp/github-actions-policy.json

# Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              Setup Complete! 🎉                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
print_success "GitHub Actions CI/CD is now configured!"
echo ""
echo "Next steps:"
echo "  1. Commit and push the .github/workflows directory to your repository"
echo "  2. Create a pull request to test the PR validation workflow"
echo "  3. Merge to main to trigger automatic deployment"
echo ""
echo "Workflow files created:"
echo "  - .github/workflows/deploy.yml         (Main deployment)"
echo "  - .github/workflows/deploy-web.yml     (Web interface)"
echo "  - .github/workflows/trigger-training.yml (Model training)"
echo "  - .github/workflows/rollback.yml       (Rollback)"
echo "  - .github/workflows/pr-validation.yml  (PR validation)"
echo ""
echo "Documentation:"
echo "  - docs/GITHUB_ACTIONS_CICD_GUIDE.md"
echo ""
print_success "Setup script completed successfully!"
