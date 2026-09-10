# ERP Solution - Enterprise Resource Planning System

A comprehensive, production-ready ERP system built with FastAPI backend and React frontend, featuring modular architecture, AI integration, and complete DevOps automation.

## 🚀 Quick Start

### Development Setup
```bash
# Clone and configure
cp .env.example .env
docker-compose up -d

# Access services
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# pgAdmin: http://localhost:5050
# RedisInsight: http://localhost:8081
```

### Production Deployment
```bash
# Configure environment
cp .env.production .env

# Deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Or deploy to Kubernetes
kubectl apply -k infra/k8s/overlays/production/
```

## 🏗️ Architecture

### Core Services
- **Backend**: FastAPI (Python) - 101 API endpoints across 15 modules
- **Frontend**: React 18 with TypeScript - Multi-module SPA
- **Database**: PostgreSQL 15 with full-text search
- **Cache**: Redis 7 for sessions and caching
- **AI**: Ollama for local LLM integration
- **Reverse Proxy**: Nginx with SSL termination

### Modules
- Authentication & Authorization (JWT + RBAC)
- CRM (Customer Relationship Management)
- HR (Human Resources)
- Inventory & Supply Chain
- Finance & Accounting
- Projects & Tasks
- Documents & Knowledge Base
- Analytics & BI Dashboard
- POS (Point of Sale)
- MRP (Material Requirements Planning)
- E-commerce Integration
- Workflows & Automation
- WebSocket Real-time Features
- AI-Powered Insights

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Python 3.11, SQLAlchemy, Pydantic |
| Frontend | React 18, TypeScript, TailwindCSS, Redux Toolkit |
| Database | PostgreSQL 15, Redis 7 |
| AI/ML | Ollama, LangChain |
| DevOps | Docker, Kubernetes, GitHub Actions |
| Monitoring | Prometheus, Grafana (optional) |

## 📦 Infrastructure

### Docker Compose
- `docker-compose.yml` - Development environment with devtools
- `docker-compose.prod.yml` - Production-ready with scaling

### Kubernetes
- Base configurations in `infra/k8s/base/`
- Environment overlays: development, staging, production
- Auto-scaling (HPA), network policies, RBAC

### CI/CD
- Automated testing on PR
- Security scanning (CodeQL, Snyk)
- Container builds and pushes
- Automated deployments

## 🔐 Security Features

- JWT authentication with refresh tokens
- Role-Based Access Control (RBAC)
- Rate limiting (configurable per environment)
- CORS protection
- SQL injection prevention
- XSS protection
- Container security scanning
- Secret management via environment variables

## 📊 Monitoring & Observability

- Health check endpoints on all services
- Prometheus metrics exposure
- Structured JSON logging
- Request tracing support
- Database query logging (dev)

## 🚀 Deployment Options

1. **Local Development**: Docker Compose
2. **Single Server**: Docker Compose Production
3. **Cloud Native**: Kubernetes cluster
4. **Hybrid**: K3s/K3d for edge deployments

## 📝 Documentation

- [Architecture Decisions](docs/ARCHITECTURE_DECISIONS.md)
- [API Summary](docs/API_SUMMARY.md)
- [Database Migrations](docs/DATABASE_MIGRATIONS.md)
- [Production Setup](docs/PRODUCTION_SETUP.md)
- [Testing Guide](docs/TESTING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## 🔧 Configuration

See `.env.example` for all available configuration options:
- Database connection
- Redis settings
- JWT secrets
- Feature flags
- AI model configuration
- Rate limiting

## 🤝 Contributing

1. Create feature branch from `main`
2. Make changes with tests
3. Ensure CI passes
4. Submit pull request

## 📄 License

MIT License - see LICENSE file for details.

---

**Status**: ✅ Production Ready
**Version**: 2.1.0
**Last Updated**: 2024
