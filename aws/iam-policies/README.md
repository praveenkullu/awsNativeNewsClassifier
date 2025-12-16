# IAM Policies for ML News Categorization Deployment

This directory contains IAM policy documents required for deploying the ML News Categorization system to AWS.

## Policy Files

### 1. `deployment-policy.json` - Full Hybrid/ECS Deployment
**Required for:** Hybrid Lambda + ECS or Pure ECS architecture

**Services covered:**
- S3 (models and data storage)
- ECR (Docker container registry)
- ECS (container orchestration)
- Lambda (serverless functions)
- RDS (PostgreSQL database)
- DynamoDB (alternative database)
- API Gateway (HTTP API)
- VPC/Networking (subnets, security groups)
- ELB (Application Load Balancer)
- CloudWatch (logs and metrics)
- SageMaker (ML training)
- IAM (role management)
- SSM Parameter Store (configuration)
- Secrets Manager (sensitive data)

**Estimated Monthly Cost:** $45-90/month

---

### 2. `ec2-minimal-policy.json` - EC2 Single Instance Deployment
**Required for:** Simple EC2 + Docker Compose deployment

**Services covered:**
- EC2 (virtual machine)
- S3 (models and data storage)
- SageMaker (ML training)
- IAM (instance profiles)
- CloudWatch Logs (logging)

**Estimated Monthly Cost:** $15-25/month

---

## How to Apply These Policies

### Option A: Attach to Your Existing User (Recommended)

**Step 1: Send policy to AWS Administrator**

Send this email to your AWS administrator:

```
Subject: IAM Policy Request for ML News Categorization Project

Hi [Admin Name],

I need additional AWS permissions to deploy the ML News Categorization system.

Please attach one of the following policies to my IAM user (rootuser):

For Hybrid/ECS deployment (production-ready):
- Policy file: deployment-policy.json
- Services: Lambda, ECS, RDS, S3, SageMaker, etc.

OR

For EC2 deployment (simpler, lower cost):
- Policy file: ec2-minimal-policy.json
- Services: EC2, S3, SageMaker

The policy files are attached. Please create a new managed policy and attach it to my user.

Account ID: 289140051471
User: rootuser
Region: us-east-2

Thank you!
```

**Step 2: Administrator applies the policy**

Your administrator will:

```bash
# Create the policy
aws iam create-policy \
  --policy-name MLNewsDeploymentPolicy \
  --policy-document file://deployment-policy.json

# Attach to your user
aws iam attach-user-policy \
  --user-name rootuser \
  --policy-arn arn:aws:iam::289140051471:policy/MLNewsDeploymentPolicy
```

**Step 3: Verify permissions**

After the administrator applies the policy, verify:

```bash
# Test RDS access
aws rds describe-db-instances --region us-east-2

# Test Lambda access
aws lambda list-functions --region us-east-2

# Test ECS access
aws ecs list-clusters --region us-east-2
```

---

### Option B: Create IAM Role for Deployments

If your administrator prefers, you can use an IAM role instead:

**Step 1: Administrator creates role**

```bash
# Create trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::289140051471:user/rootuser"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name MLNewsDeploymentRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policy to role
aws iam create-policy \
  --policy-name MLNewsDeploymentPolicy \
  --policy-document file://deployment-policy.json

aws iam attach-role-policy \
  --role-name MLNewsDeploymentRole \
  --policy-arn arn:aws:iam::289140051471:policy/MLNewsDeploymentPolicy
```

**Step 2: Assume the role when deploying**

```bash
# Assume role
aws sts assume-role \
  --role-arn arn:aws:iam::289140051471:role/MLNewsDeploymentRole \
  --role-session-name ml-news-deployment

# Use temporary credentials for deployment
export AWS_ACCESS_KEY_ID=<from assume-role output>
export AWS_SECRET_ACCESS_KEY=<from assume-role output>
export AWS_SESSION_TOKEN=<from assume-role output>
```

---

## Policy Comparison

| Feature | deployment-policy.json | ec2-minimal-policy.json |
|---------|------------------------|-------------------------|
| **Complexity** | High | Low |
| **Services** | 15+ AWS services | 5 AWS services |
| **Cost** | $45-90/month | $15-25/month |
| **Scalability** | Auto-scales | Manual scaling |
| **High Availability** | Yes (multi-AZ) | No (single instance) |
| **Setup Time** | 30-60 minutes | 10-15 minutes |
| **Maintenance** | Managed services | Some manual work |
| **Best For** | Production | Development/Testing |

---

## Security Best Practices

The policies follow these security principles:

### 1. **Least Privilege**
- Resources are scoped to `ml-news-*` naming pattern
- Only necessary actions are granted
- Region-specific when possible (us-east-2)

### 2. **Resource Restrictions**
```json
"Resource": [
  "arn:aws:s3:::ml-news-*",           // Only ml-news buckets
  "arn:aws:lambda:*:*:function:ml-news-*", // Only ml-news functions
  "arn:aws:rds:*:*:db:ml-news-*"      // Only ml-news databases
]
```

### 3. **Action Restrictions**
- No `*:*` wildcards
- Specific actions listed
- No destructive global actions

### 4. **Recommended Enhancements**

After initial deployment, consider adding:

**Condition-based restrictions:**
```json
{
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "us-east-2"
    }
  }
}
```

**MFA requirement for deletions:**
```json
{
  "Condition": {
    "Bool": {
      "aws:MultiFactorAuthPresent": "true"
    }
  },
  "Action": [
    "rds:DeleteDBInstance",
    "s3:DeleteBucket"
  ]
}
```

---

## Troubleshooting

### Permission Denied Errors

If you get permission errors after applying policies:

1. **Wait 1-2 minutes** - IAM changes can take time to propagate

2. **Verify policy is attached:**
```bash
aws iam list-attached-user-policies --user-name rootuser
```

3. **Check for typos in resource ARNs:**
- Correct account ID: `289140051471`
- Correct region: `us-east-2`
- Correct naming: `ml-news-*`

4. **Test specific service:**
```bash
# Test each service individually
aws s3 ls
aws rds describe-db-instances --region us-east-2
aws lambda list-functions --region us-east-2
aws ecs list-clusters --region us-east-2
```

### Common Issues

**Issue:** "User is not authorized to perform X"
- **Solution:** Service not in policy. Add to appropriate statement.

**Issue:** "Access Denied" on resource creation
- **Solution:** Check resource naming matches `ml-news-*` pattern

**Issue:** "Cannot pass role to service"
- **Solution:** Add `iam:PassRole` permission with specific role ARN

---

## Next Steps

After IAM policies are applied:

### For Hybrid/ECS Deployment:
```bash
# Resume deployment
cd /path/to/ml-news-categorization

# Continue from where we left off
# You'll be able to create RDS, Lambda, ECS resources
```

### For EC2 Deployment:
```bash
# Launch EC2 instance
./scripts/deploy-ec2.sh

# Or use AWS Console to launch with:
# - Instance type: t3.small
# - AMI: Amazon Linux 2
# - IAM role: ml-news-ec2-role
# - User data: scripts/ec2-userdata.sh
```

---

## Cost Alerts (Recommended)

Ask your administrator to set up billing alerts:

```bash
# Create SNS topic for alerts
aws sns create-topic --name ml-news-billing-alerts

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:289140051471:ml-news-billing-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# Create CloudWatch alarm for $50/month threshold
aws cloudwatch put-metric-alarm \
  --alarm-name ml-news-cost-alarm \
  --alarm-description "Alert when ML News costs exceed $50" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 21600 \
  --evaluation-periods 1 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:289140051471:ml-news-billing-alerts
```

---

## Questions?

If you have questions about these policies:
1. Review the policy file comments
2. Check AWS IAM documentation: https://docs.aws.amazon.com/iam/
3. Test permissions incrementally
4. Ask your AWS administrator for help

**Important:** Always test in a development environment first before applying to production!
