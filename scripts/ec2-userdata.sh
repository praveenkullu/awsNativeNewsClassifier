#!/bin/bash
set -e

# Log all output
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=== ML News Categorization Setup Started at $(date) ==="

# Update system
echo "Updating system packages..."
yum update -y

# Install Docker
echo "Installing Docker..."
yum install docker -y
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
echo "Installing Docker Compose..."
curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Install Git
echo "Installing Git..."
yum install git -y

# Clone repository
echo "Cloning repository..."
cd /home/ec2-user
sudo -u ec2-user git clone https://github.com/praveenkullu/temp_tincsi_pf_news_2.git ml-news-categorization
cd ml-news-categorization

# Create environment file
echo "Creating environment file..."
cat > .env << 'EOF'
# Database
POSTGRES_USER=mlnews
POSTGRES_PASSWORD=mlnews_secure_password_$(openssl rand -hex 8)
POSTGRES_DB=mlnews

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# AWS Configuration
AWS_REGION=us-east-2
S3_MODEL_BUCKET=ml-news-models-289140051471

# Model Configuration
MODEL_VERSION=latest
PERFORMANCE_THRESHOLD=0.75
CORRECTION_THRESHOLD=100

# Service URLs
INFERENCE_SERVICE_URL=http://inference-service:8001
FEEDBACK_SERVICE_URL=http://feedback-service:8002
MODEL_SERVICE_URL=http://model-service:8003
EVALUATION_SERVICE_URL=http://evaluation-service:8004

# Logging
LOG_LEVEL=INFO
EOF

# Set ownership
chown -R ec2-user:ec2-user /home/ec2-user/ml-news-categorization

# Start services
echo "Starting Docker Compose services..."
cd /home/ec2-user/ml-news-categorization
sudo -u ec2-user docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to start..."
sleep 30

# Configure systemd service for auto-restart
echo "Configuring systemd service..."
cat > /etc/systemd/system/ml-news.service << 'SERVICEEOF'
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
User=ec2-user
Group=ec2-user

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable ml-news.service

# Display status
echo "=== Setup Complete at $(date) ==="
echo "Checking service status..."
docker ps

echo "=== Deployment Summary ==="
echo "Repository: https://github.com/praveenkullu/temp_tincsi_pf_news_2.git"
echo "Working Directory: /home/ec2-user/ml-news-categorization"
echo "API Gateway: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
echo "Health Check: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000/health"
echo ""
echo "To view logs: docker-compose -f /home/ec2-user/ml-news-categorization/docker-compose.yml logs -f"
echo "=== End of Setup ==="
