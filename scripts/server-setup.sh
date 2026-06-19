#!/bin/bash
###############################################################################
# ERP SOLUTION — Production Server Setup
# Run on Ubuntu 22.04 LTS
###############################################################################

set -e

echo "=========================================="
echo "  ERP SOLUTION Production Server Setup"
echo "=========================================="

# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Kubernetes tools (kubectl, helm)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install certbot for SSL
sudo apt-get install -y certbot python3-certbot-nginx

# Create app directory
mkdir -p /opt/erp-solution
cd /opt/erp-solution

# Pull images
docker pull powerrangeranikg/erp-solution-backend:latest
docker pull powerrangeranikg/erp-solution-frontend:latest

# Start services
docker-compose up -d

# Setup SSL
certbot --nginx -d api.erpsolution.com -d app.erpsolution.com

# Enable firewall
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

echo "=========================================="
echo "  Setup Complete!"
echo "  Backend: https://api.erpsolution.com"
echo "  Frontend: https://app.erpsolution.com"
echo "=========================================="
