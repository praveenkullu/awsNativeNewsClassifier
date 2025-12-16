#!/bin/bash
# Build Lambda packages using Docker for correct dependencies

SERVICE=$1
if [ -z "$SERVICE" ]; then
    echo "Usage: $0 <service-name>"
    echo "Example: $0 model-service"
    exit 1
fi

cd services/$SERVICE

# Clean up old packages
rm -rf package lambda-deploy.zip

# Use Amazon Linux 2 (same as Lambda runtime)
docker run --rm \
    --entrypoint /bin/bash \
    -v "$PWD":/var/task \
    public.ecr.aws/lambda/python:3.10 \
    -c "
        cd /var/task &&
        mkdir -p package &&
        pip install -r requirements.txt -t package/ --upgrade &&
        pip install mangum -t package/ &&
        cp -r app package/ &&
        [ -f lambda_handler.py ] && cp lambda_handler.py package/ &&
        cd package && zip -r ../lambda-deploy.zip . -q
    "

echo "✓ Package built: $(du -h lambda-deploy.zip | cut -f1)"
