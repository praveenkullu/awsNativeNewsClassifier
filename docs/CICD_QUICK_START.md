# CI/CD Quick Start Guide

## 🚀 Quick Setup (5 Minutes)

### Prerequisites
- AWS Account with admin access
- GitHub repository
- AWS CLI configured
- GitHub CLI installed (optional but recommended)

### Step 1: Run Setup Script

```bash
# Navigate to project root
cd /path/to/temp_tincsi_pf_news_2

# Set your GitHub username/org
export GITHUB_ORG="your-github-username"

# Run setup script
./scripts/setup-github-actions.sh
```

This script will:
- ✅ Create GitHub OIDC provider in AWS
- ✅ Create IAM role with required permissions
- ✅ Configure GitHub repository secrets
- ✅ Verify all AWS resources exist

### Step 2: Commit Workflow Files

```bash
# Add workflow files
git add .github/workflows/

# Commit
git commit -m "ci: add GitHub Actions workflows"

# Push to GitHub
git push origin main
```

### Step 3: Test the Pipeline

```bash
# Option 1: Create a test PR
git checkout -b test/ci-cd
echo "# Test" >> README.md
git add README.md
git commit -m "test: verify CI/CD pipeline"
git push origin test/ci-cd

# Create PR on GitHub
# GitHub Actions will automatically run PR validation

# Option 2: Manual workflow trigger
# Go to GitHub → Actions → Deploy ML News Services → Run workflow
```

---

## 📋 Manual Setup (If Script Fails)

### 1. Create OIDC Provider

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### 2. Create IAM Role

```bash
# Replace YOUR-GITHUB-ORG and YOUR-REPO
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::289140051471:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR-GITHUB-ORG/YOUR-REPO:*"
        }
      }
    }
  ]
}
EOF

aws iam create-role \
  --role-name GitHubActionsMLNewsRole \
  --assume-role-policy-document file://trust-policy.json
```

### 3. Attach Policies

```bash
# Attach managed policies
aws iam attach-role-policy \
  --role-name GitHubActionsMLNewsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
  --role-name GitHubActionsMLNewsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess

# Create and attach custom policy (see full policy in setup script)
```

### 4. Add GitHub Secrets

Go to: `https://github.com/YOUR-ORG/YOUR-REPO/settings/secrets/actions`

Add these secrets:

| Secret Name | Value |
|------------|-------|
| AWS_ACCOUNT_ID | 289140051471 |
| AWS_REGION | us-east-2 |
| AWS_ROLE_ARN | arn:aws:iam::289140051471:role/GitHubActionsMLNewsRole |
| ECR_REPOSITORY | ml-news-inference |
| ECS_CLUSTER | ml-news-cluster |
| ECS_SERVICE | ml-news-inference-service |
| S3_WEB_BUCKET | ml-news-web-interface-289140051471 |
| API_GATEWAY_URL | https://w6of479oic.execute-api.us-east-2.amazonaws.com |

---

## 🔄 Workflow Overview

### 1. Main Deployment (`deploy.yml`)

**Triggers:**
- Push to `main` branch
- Manual trigger via GitHub Actions UI

**What it does:**
1. Runs tests for all services
2. Builds Lambda packages using Docker
3. Builds and pushes Docker image to ECR
4. Deploys Lambda functions
5. Deploys ECS service
6. Runs smoke tests

**Approximate Duration:** 10-15 minutes

### 2. Web Interface Deployment (`deploy-web.yml`)

**Triggers:**
- Push to `main` with changes to `services/api-gateway/static/**`
- Manual trigger

**What it does:**
1. Updates API Gateway URL in JavaScript
2. Syncs static files to S3
3. Sets correct content types
4. Verifies deployment

**Approximate Duration:** 1-2 minutes

### 3. Model Training Trigger (`trigger-training.yml`)

**Triggers:**
- Manual trigger
- Scheduled (weekly on Sunday at 2 AM UTC)

**What it does:**
1. Triggers SageMaker training job via API
2. Monitors training progress
3. Reports metrics
4. Reloads model in inference service

**Approximate Duration:** 30-60 minutes (depends on training time)

### 4. Rollback (`rollback.yml`)

**Triggers:**
- Manual trigger only

**What it does:**
1. Rolls back selected service to previous version
2. Verifies rollback with health checks

**Approximate Duration:** 3-5 minutes

### 5. PR Validation (`pr-validation.yml`)

**Triggers:**
- Pull request to `main` or `develop`

**What it does:**
1. Validates PR title format
2. Checks for large files and secrets
3. Runs linters on changed files
4. Runs tests for affected services
5. Auto-labels PR by size and components

**Approximate Duration:** 3-5 minutes

---

## 🎯 Common Tasks

### Deploy Everything to Production

```bash
# Make your changes
git checkout -b feature/my-changes
# ... make changes ...
git add .
git commit -m "feat: add new feature"
git push origin feature/my-changes

# Create PR and merge to main
# GitHub Actions automatically deploys after merge
```

### Deploy Only Web Interface

```bash
# Method 1: Push changes to static files
git add services/api-gateway/static/
git commit -m "feat: update UI"
git push origin main

# Method 2: Manual trigger
# Go to Actions → Deploy Web Interface → Run workflow
```

### Trigger Model Training

```bash
# Go to GitHub Actions → Trigger Model Training → Run workflow
# Select parameters:
#   - Model type: logistic_regression
#   - Include feedback: true
#   - Description: "Monthly retraining"
```

### Rollback a Failed Deployment

```bash
# Go to GitHub Actions → Rollback Deployment → Run workflow
# Select:
#   - Service: all (or specific service)
#   - Version: leave empty for previous
```

### View Deployment Logs

```bash
# Go to GitHub → Actions → Click on workflow run
# View logs for each job
```

---

## 🔧 Troubleshooting

### Workflow Fails with "Unable to assume role"

**Problem:** GitHub Actions can't authenticate with AWS

**Solution:**
1. Verify OIDC provider exists:
   ```bash
   aws iam list-open-id-connect-providers | grep token.actions.githubusercontent.com
   ```

2. Check IAM role trust policy includes your repo:
   ```bash
   aws iam get-role --role-name GitHubActionsMLNewsRole
   ```

3. Verify GitHub secret `AWS_ROLE_ARN` is correct

### Lambda Deployment Fails

**Problem:** Lambda package too large or deployment timeout

**Solution:**
1. Check Lambda logs in CloudWatch
2. Verify package size in workflow logs
3. Ensure Docker-based build is working
4. Check Lambda execution role permissions

### ECS Deployment Timeout

**Problem:** ECS service doesn't stabilize

**Solution:**
1. Check ECS task logs in CloudWatch
2. Verify Docker image is valid
3. Check task definition environment variables
4. Review security group and VPC settings

### Smoke Tests Fail

**Problem:** API endpoints return errors after deployment

**Solution:**
1. Check service health in AWS Console
2. View CloudWatch logs for all services
3. Verify environment variables are set
4. Check API Gateway configuration

---

## 📊 Workflow Status Badges

Add these to your README.md:

```markdown
![Deploy](https://github.com/YOUR-ORG/YOUR-REPO/actions/workflows/deploy.yml/badge.svg)
![PR Validation](https://github.com/YOUR-ORG/YOUR-REPO/actions/workflows/pr-validation.yml/badge.svg)
```

---

## 🔐 Security Best Practices

### ✅ What's Already Configured

- **OIDC Authentication**: No long-lived AWS credentials in GitHub
- **Least Privilege IAM**: Role only has required permissions
- **Secret Management**: Sensitive data in GitHub Secrets
- **Branch Protection**: Can be enabled in GitHub settings

### 🛡️ Recommended Additional Security

1. **Enable Branch Protection Rules**
   ```
   GitHub → Settings → Branches → Add rule
   - Require pull request reviews
   - Require status checks to pass
   - Require signed commits
   ```

2. **Enable Dependabot**
   ```
   GitHub → Settings → Security & analysis → Enable Dependabot
   ```

3. **Add CODEOWNERS**
   ```bash
   echo "* @your-team" > .github/CODEOWNERS
   ```

4. **Enable Secret Scanning**
   ```
   GitHub → Settings → Security & analysis → Enable secret scanning
   ```

---

## 📈 Monitoring and Notifications

### Add Slack Notifications

1. Create Slack webhook: https://api.slack.com/messaging/webhooks

2. Add to GitHub Secrets:
   ```bash
   gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/..."
   ```

3. Workflows automatically use it if set

### CloudWatch Dashboards

View deployment metrics:
```bash
# Open CloudWatch console
open https://console.aws.amazon.com/cloudwatch/home?region=us-east-2

# Create dashboard with:
# - Lambda invocations and errors
# - ECS service CPU/memory
# - API Gateway requests
# - Training job metrics
```

---

## 🆘 Getting Help

### Check Workflow Status
```bash
# List recent workflow runs
gh run list --repo YOUR-ORG/YOUR-REPO

# View specific run
gh run view RUN_ID --repo YOUR-ORG/YOUR-REPO

# View logs
gh run view RUN_ID --log --repo YOUR-ORG/YOUR-REPO
```

### Common Commands
```bash
# Re-run failed workflow
gh run rerun RUN_ID --repo YOUR-ORG/YOUR-REPO

# Cancel running workflow
gh run cancel RUN_ID --repo YOUR-ORG/YOUR-REPO

# Download artifacts
gh run download RUN_ID --repo YOUR-ORG/YOUR-REPO
```

---

## 📚 Additional Resources

- [Complete Guide](./GITHUB_ACTIONS_CICD_GUIDE.md) - Detailed documentation
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [AWS OIDC Guide](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Deployment Guide](../DEPLOYMENT_GUIDE.md) - AWS infrastructure setup

---

## ✅ Verification Checklist

After setup, verify:

- [ ] OIDC provider exists in AWS
- [ ] IAM role has correct trust policy
- [ ] All GitHub secrets are configured
- [ ] Workflow files are committed
- [ ] PR validation works on test PR
- [ ] Main deployment works after merge
- [ ] Smoke tests pass
- [ ] Rollback procedure tested
- [ ] Team members have access

---

**Questions or Issues?**
- Check the [full guide](./GITHUB_ACTIONS_CICD_GUIDE.md)
- Review GitHub Actions logs
- Check AWS CloudWatch logs
- Verify all secrets are correct
