#!/bin/bash
###############################################################################
# ERP SOLUTION — Production Deployment Script
# Usage: ./scripts/deploy-production.sh [server_ip]
###############################################################################

set -e

SERVER_IP="${1:-}"
DOCKER_USERNAME="powerrangeranikg"

echo "=========================================="
echo "  ERP SOLUTION — Production Deployment"
echo "=========================================="
echo ""

if [ -z "$SERVER_IP" ]; then
    echo "Usage: ./scripts/deploy-production.sh [server_ip]"
    echo "Example: ./scripts/deploy-production.sh 192.168.1.100"
    exit 1
fi

echo "Deploying to: $SERVER_IP"
echo ""

# Step 1: SSH to server and setup
info "[1/5] Setting up server..."
ssh root@$SERVER_IP << 'REMOTE'
    # Update system
    apt-get update && apt-get upgrade -y

    # Install Docker
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker $USER

    # Install Docker Compose
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    # Create app directory
    mkdir -p /opt/erp-solution
    cd /opt/erp-solution

    # Create docker-compose for production
    cat > docker-compose.yml << 'EOF'
version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: erp
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
      POSTGRES_DB: erp_solution
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U erp"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    image: powerrangeranikg/erp-solution-backend:latest
    environment:
      DATABASE_URL: postgresql://erp:${DB_PASSWORD:-changeme}@postgres:5432/erp_solution
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY:-change-me-in-production}
      ENVIRONMENT: production
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    image: powerrangeranikg/erp-solution-frontend:latest
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: http://localhost:8000

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
EOF

    # Create nginx config
    cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }

    upstream frontend {
        server frontend:3000;
    }

    server {
        listen 80;
        server_name _;

        location /api {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
EOF

    echo "Server setup complete!"
REMOTE

info "[2/5] Server setup complete"

# Step 2: Pull latest images
info "[3/5] Pulling Docker images..."
ssh root@$SERVER_IP "docker pull $DOCKER_USERNAME/erp-solution-backend:latest && docker pull $DOCKER_USERNAME/erp-solution-frontend:latest"

info "[4/5] Images pulled"

# Step 3: Start services
info "[5/5] Starting services..."
ssh root@$SERVER_IP "cd /opt/erp-solution && docker-compose up -d"

info "[✓] Deployment complete!"

echo ""
echo "=========================================="
echo "  Production Deployment Complete!"
echo "=========================================="
echo ""
echo "  Server: $SERVER_IP"
echo "  Backend: http://$SERVER_IP:8000"
echo "  Frontend: http://$SERVER_IP:3000"
echo "  API Docs: http://$SERVER_IP:8000/docs"
echo ""
echo "  Next steps:"
echo "  1. Configure SSL with Let's Encrypt"
echo "  2. Set up domain DNS"
echo "  3. Configure firewall rules"
echo "  4. Monitor with ./scripts/health-check.sh"
echo ""
