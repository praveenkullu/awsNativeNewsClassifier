# CI/CD Comparison for ML News Categorization

## Overview

This document compares CI/CD implementation across different architecture options, with focus on **Option B (Hybrid Lambda + ECS)**.

---

## CI/CD Workflow Comparison

### Option A: Pure Serverless (Lambda)

**Deployment Flow:**
```
Code Push → Build → Package ZIPs → Deploy Lambda → Test
```

**Pros:**
- ✅ **Simplest deployment** - Just ZIP files, no Docker
- ✅ **Fastest deployment** - Lambda updates in ~10 seconds
- ✅ **Built-in versioning** - Lambda versions and aliases
- ✅ **Easy rollback** - Switch alias to previous version
- ✅ **Canary deployments** - Traffic shifting built-in

**Cons:**
- ❌ Code changes needed (add Lambda handlers)
- ❌ Different local dev environment
- ❌ Cold start testing required

**Deployment Time:** ~2 minutes

---

### Option B: Hybrid (Lambda + ECS) ⭐ RECOMMENDED

**Deployment Flow:**
```
Code Push → Build & Test → Package Lambdas + Build Docker → Deploy Both → Smoke Tests
```

**Pros:**
- ✅ **Best of both worlds** - Fast Lambda updates + Warm ECS
- ✅ **Independent deployments** - Can deploy services separately
- ✅ **No ECS deployment for most changes** - Feedback/Model/Eval are Lambda
- ✅ **Faster than pure ECS** - Only 1 ECS service to update vs 5
- ✅ **Easy feature flags** - Use Lambda aliases for gradual rollout
- ✅ **Cost-effective** - Lambda scales to zero, ECS always warm

**Cons:**
- ⚠️ Two deployment mechanisms to manage
- ⚠️ Slightly more complex pipeline

**Deployment Time:**
- Lambda only: ~2 minutes
- ECS only: ~4-5 minutes
- Both: ~6 minutes

**Why This Works Great:**

1. **Inference service rarely changes** - Once trained, it's stable
2. **Lambda services change frequently** - Business logic, feedback rules, evaluation criteria
3. **Fast feedback loop** - Most changes deploy in 2 minutes
4. **Zero downtime** - Rolling updates for ECS, traffic shifting for Lambda

---

### Option C: Single EC2

**Deployment Flow:**
```
Code Push → Build → SSH to EC2 → Pull code → docker-compose up → Test
```

**Pros:**
- ✅ Simple deployment script
- ✅ Same as local environment

**Cons:**
- ❌ Manual process or complex automation
- ❌ Downtime during deployment
- ❌ Single point of failure
- ❌ No built-in rollback
- ❌ SSH key management

**Deployment Time:** ~5-10 minutes (with downtime)

---

### Option D: Pure ECS (5 Services)

**Deployment Flow:**
```
Code Push → Build 5 Images → Push to ECR → Update 5 ECS Services → Wait for stability
```

**Pros:**
- ✅ No code changes needed
- ✅ Production-grade infrastructure

**Cons:**
- ❌ **Slowest deployments** - Need to build/push/deploy 5 images
- ❌ **Higher cost** - 5 tasks running 24/7
- ❌ **Complex rollback** - Need to manage 5 service versions
- ❌ **Longer CI/CD pipeline** - 15-20 minutes total

**Deployment Time:** ~15-20 minutes

---

## Detailed CI/CD Features Comparison

| Feature | Option A (Lambda) | Option B (Hybrid) | Option C (EC2) | Option D (ECS) |
|---------|-------------------|-------------------|----------------|----------------|
| **Deployment Speed** | ⚡ 2 min | ⚡⚡ 2-6 min | 🐌 5-10 min | 🐌🐌 15-20 min |
| **Zero Downtime** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Blue/Green Support** | ✅ Native | ✅ Native | ❌ Manual | ✅ CodeDeploy |
| **Canary Deployments** | ✅ Built-in | ✅ Lambda only | ❌ No | ⚠️ Complex |
| **Rollback Time** | ⚡ 10 seconds | ⚡ 10s-2min | 🐌 5-10 min | 🐌 5-10 min |
| **Versioning** | ✅ Automatic | ✅ Automatic | ❌ Manual | ✅ Task Def |
| **Independent Service Deploy** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Complexity** | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ |
| **GitHub Actions Time** | ~5 min | ~10 min | ~8 min | ~20 min |
| **Docker Build Required** | ❌ No | ⚠️ 1 service | ❌ No | ✅ 5 services |
| **ECR Push Required** | ❌ No | ⚠️ 1 image | ❌ No | ✅ 5 images |

---

## Option B (Hybrid) - Detailed CI/CD Flow

### 1. Code Changes & Testing (3-5 minutes)

```
┌─────────────────────────────────────────────────────────┐
│  Parallel Testing                                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │  Lambda    │  │  ECS       │  │  Lint &    │       │
│  │  Services  │  │  Service   │  │  Format    │       │
│  │  Tests     │  │  Tests     │  │  Check     │       │
│  │  (3 svcs)  │  │  (1 svc)   │  │            │       │
│  └────────────┘  └────────────┘  └────────────┘       │
│       2m              2m              1m               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2. Build & Package (2-3 minutes)

```
┌─────────────────────────────────────────────────────────┐
│  Parallel Build                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐       ┌──────────────────┐        │
│  │  Package        │       │  Build & Push    │        │
│  │  Lambda ZIPs    │       │  Docker Image    │        │
│  │  (3 services)   │       │  to ECR          │        │
│  │                 │       │  (1 image)       │        │
│  └─────────────────┘       └──────────────────┘        │
│       1m                         3m                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3. Deployment (2-4 minutes)

**Scenario A: Only Lambda Changes** (~2 minutes)
```bash
# Most common case - business logic changes
git push
  → Test Lambda services
  → Package ZIPs
  → Update Lambda functions (10s each)
  → Done! ✅

Total: ~2 minutes
```

**Scenario B: Only ECS Changes** (~4 minutes)
```bash
# Model inference improvements
git push
  → Test inference service
  → Build Docker image
  → Push to ECR
  → Update ECS task definition
  → Rolling update (0 downtime)
  → Done! ✅

Total: ~4-5 minutes
```

**Scenario C: Both Changed** (~6 minutes)
```bash
# Full system update
git push
  → Test all services (parallel)
  → Build Lambda ZIPs + Docker (parallel)
  → Deploy Lambda functions (30s)
  → Deploy ECS service (4m)
  → Smoke tests
  → Done! ✅

Total: ~6 minutes
```

### 4. Advanced Deployment Strategies

#### Canary Deployment (Lambda Services)
```bash
# Deploy new version with 10% traffic
aws lambda update-alias \
  --function-name ml-news-feedback \
  --name live \
  --routing-config AdditionalVersionWeights={"2"=0.1}

# Monitor CloudWatch metrics for 10 minutes
# If good, shift 100% traffic
aws lambda update-alias \
  --function-name ml-news-feedback \
  --name live \
  --function-version 2
```

#### Blue/Green Deployment (ECS)
```bash
# Use AWS CodeDeploy for ECS
# Automatically creates new task set
# Gradually shifts traffic
# Can rollback instantly if issues detected
```

---

## Real-World CI/CD Example

### Day 1: Add new feedback category
```
Change: Update feedback-service logic
Deploy: Lambda only
Time: 2 minutes
Impact: Zero downtime, instant rollback available
```

### Day 2: Improve model preprocessing
```
Change: Update inference-service preprocessing
Deploy: ECS only
Time: 5 minutes
Impact: Rolling update, zero downtime
```

### Day 3: Change evaluation threshold
```
Change: Update evaluation-service configuration
Deploy: Lambda only
Time: 2 minutes
Impact: Instant update via environment variables
```

### Week 2: Major model retrain
```
Change: SageMaker training, update inference service
Deploy: SageMaker job + ECS update
Time: Training: 2 hours, Deploy: 5 minutes
Impact: New model artifact in S3, ECS picks up automatically
```

---

## Monitoring & Debugging

### Lambda Services
```yaml
Logs: CloudWatch Logs (/aws/lambda/ml-news-*)
Metrics:
  - Invocations
  - Duration
  - Errors
  - Throttles
Tracing: X-Ray (optional)
Debugging: Lambda console, CloudWatch Insights
```

### ECS Service
```yaml
Logs: CloudWatch Logs (/ecs/ml-news-inference)
Metrics:
  - CPU/Memory utilization
  - Request count
  - Response time
Tracing: X-Ray (optional)
Debugging: ECS console, exec into container
```

---

## Cost Comparison - CI/CD

| Architecture | ECR Storage | Build Minutes (GH) | Monthly CI/CD Cost |
|--------------|-------------|--------------------|--------------------|
| Option A | $0 | ~200 min | ~$0 |
| **Option B** | **$1** | **~400 min** | **~$0** |
| Option C | $0 | ~300 min | ~$0 |
| Option D | $5 | ~800 min | ~$0 |

*GitHub Actions: 2000 free minutes/month for public repos*

---

## Rollback Comparison

### Lambda (Options A & B)
```bash
# Instant rollback (10 seconds)
aws lambda update-alias \
  --function-name ml-news-feedback \
  --name live \
  --function-version PREVIOUS

# Or use console: One click rollback
```

### ECS (Options B & D)
```bash
# Rollback to previous task definition (3-5 minutes)
aws ecs update-service \
  --cluster ml-news-cluster \
  --service ml-news-inference \
  --task-definition ml-news-inference:PREVIOUS \
  --force-new-deployment
```

### EC2 (Option C)
```bash
# Manual rollback (5-10 minutes)
ssh ec2-instance
git reset --hard PREVIOUS_COMMIT
docker-compose up -d --build
```

---

## Recommendation: Why Option B is Best for CI/CD

### 1. **Deployment Flexibility**
- Deploy frequently changed services (feedback, evaluation) in 2 minutes
- Deploy stable inference service only when needed
- Independent deployment pipelines reduce risk

### 2. **Fast Feedback Loop**
- Most changes don't touch inference → 2-minute deploys
- Developers get fast feedback
- Can deploy multiple times per day safely

### 3. **Production-Ready Features**
- Lambda: Built-in canary, versioning, instant rollback
- ECS: Zero-downtime rolling updates, health checks
- Best of both worlds

### 4. **Cost-Effective CI/CD**
- Only build 1 Docker image (not 5)
- Lambda deploys are ZIP uploads (fast, small)
- Less ECR storage needed
- Faster GitHub Actions runs

### 5. **Easy to Maintain**
- Clear separation: Lambda = business logic, ECS = ML inference
- Can split team responsibilities
- Standard AWS patterns for both

---

## Getting Started with Option B

### Prerequisites
```bash
# Install deployment dependencies
pip install mangum  # FastAPI to Lambda adapter
pip install awscli
```

### One-Time Setup
```bash
# Create Lambda functions (Terraform/CloudFormation)
# Create ECS cluster and service
# Set up GitHub Actions secrets
```

### Daily Development
```bash
# Make changes
git commit -m "Update feedback logic"
git push origin develop

# GitHub Actions automatically:
# 1. Tests your changes
# 2. Packages Lambda
# 3. Deploys to dev environment
# 4. Runs smoke tests
# 5. Ready for production promotion
```

---

## Conclusion

**Option B (Hybrid)** provides the **best CI/CD experience** by combining:
- ⚡ **Speed**: 2-6 minute deployments
- 🛡️ **Safety**: Zero downtime, instant rollbacks
- 💰 **Cost**: Lower than pure ECS
- 🎯 **Flexibility**: Deploy services independently

**Perfect for:**
- Teams that iterate quickly
- Applications with mix of stable (ML) and dynamic (business logic) components
- Cost-conscious production deployments
- Modern DevOps practices
