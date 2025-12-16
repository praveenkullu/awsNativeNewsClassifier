#!/bin/bash
set -e

# Upload Training Data Script
# Uploads dataset to S3 for SageMaker training

REGION="us-east-2"
S3_BUCKET="ml-news-data-289140051471"
DATA_FILE="data/News_Category_Dataset_v3.json"

echo "📤 Uploading Training Data to S3"
echo "================================="

# Check if data file exists
if [ ! -f "$DATA_FILE" ]; then
    echo "⚠️  Data file not found: $DATA_FILE"
    echo ""
    echo "Please download the dataset first:"
    echo "  1. Install Kaggle CLI: pip install kaggle"
    echo "  2. Set up credentials: ~/.kaggle/kaggle.json"
    echo "  3. Download dataset:"
    echo "     kaggle datasets download -d rmisra/news-category-dataset -p data/"
    echo "     unzip data/news-category-dataset.zip -d data/"
    echo ""
    exit 1
fi

echo "Data file: $DATA_FILE"
echo "Size: $(du -h $DATA_FILE | cut -f1)"
echo ""

# Upload to S3
echo "Uploading to s3://$S3_BUCKET/data/..."
aws s3 cp $DATA_FILE s3://$S3_BUCKET/data/News_Category_Dataset_v3.json --region $REGION

echo "✅ Upload complete!"
echo ""

# Verify upload
echo "Verifying upload..."
aws s3 ls s3://$S3_BUCKET/data/ --region $REGION

echo ""
echo "════════════════════════════════════════"
echo "✅ Training Data Ready!"
echo "════════════════════════════════════════"
echo ""
echo "S3 Location: s3://$S3_BUCKET/data/News_Category_Dataset_v3.json"
echo ""
echo "Next: You can now trigger model training via API"
echo ""
