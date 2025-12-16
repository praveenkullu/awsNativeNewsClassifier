#!/bin/bash
# Script for AWS Administrator to apply IAM policies
# Usage: ./apply-policy.sh [deployment|ec2-minimal]

set -e

POLICY_TYPE=${1:-deployment}
USER_NAME="rootuser"
ACCOUNT_ID="289140051471"

echo "🔐 Applying IAM Policy for ML News Categorization"
echo "=================================================="

if [ "$POLICY_TYPE" == "deployment" ]; then
    POLICY_FILE="deployment-policy.json"
    POLICY_NAME="MLNewsFullDeploymentPolicy"
    echo "📋 Policy: Full Deployment (Hybrid/ECS)"
elif [ "$POLICY_TYPE" == "ec2-minimal" ]; then
    POLICY_FILE="ec2-minimal-policy.json"
    POLICY_NAME="MLNewsEC2Policy"
    echo "📋 Policy: EC2 Minimal"
else
    echo "❌ Invalid policy type. Use 'deployment' or 'ec2-minimal'"
    exit 1
fi

echo "👤 User: $USER_NAME"
echo "🆔 Account: $ACCOUNT_ID"
echo ""

# Check if policy file exists
if [ ! -f "$POLICY_FILE" ]; then
    echo "❌ Policy file not found: $POLICY_FILE"
    exit 1
fi

# Create or update policy
echo "Creating IAM policy..."
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

# Check if policy already exists
if aws iam get-policy --policy-arn "$POLICY_ARN" 2>/dev/null; then
    echo "⚠️  Policy already exists. Creating new version..."

    # Delete old versions if at limit (max 5 versions)
    OLD_VERSIONS=$(aws iam list-policy-versions --policy-arn "$POLICY_ARN" \
        --query 'Versions[?!IsDefaultVersion].VersionId' --output text)

    for version in $OLD_VERSIONS; do
        aws iam delete-policy-version \
            --policy-arn "$POLICY_ARN" \
            --version-id "$version" 2>/dev/null || true
    done

    # Create new version
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document "file://$POLICY_FILE" \
        --set-as-default

    echo "✅ Policy updated to new version"
else
    # Create new policy
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document "file://$POLICY_FILE" \
        --description "IAM policy for ML News Categorization deployment"

    echo "✅ Policy created: $POLICY_ARN"
fi

# Attach policy to user
echo ""
echo "Attaching policy to user $USER_NAME..."

if aws iam attach-user-policy \
    --user-name "$USER_NAME" \
    --policy-arn "$POLICY_ARN"; then
    echo "✅ Policy attached successfully"
else
    echo "⚠️  Policy may already be attached or user doesn't exist"
fi

# Verify
echo ""
echo "Verifying permissions..."
echo ""
echo "Attached policies for user $USER_NAME:"
aws iam list-attached-user-policies --user-name "$USER_NAME"

echo ""
echo "✅ Done! Permissions should be active in 1-2 minutes."
echo ""
echo "Next steps for developer:"
echo "1. Wait 1-2 minutes for IAM changes to propagate"
echo "2. Test permissions with: aws rds describe-db-instances --region us-east-2"
echo "3. Resume deployment process"
echo ""
