# ERP System - Professional Boilerplate v1.0

## 🎯 Project Status: Production Ready

A comprehensive, enterprise-grade ERP system built with modern architecture and best practices.

## 📦 What's Included

### Backend (FastAPI/Python)
- **19 Router Modules**: Auth, CRM, HR, Inventory, Finance, Projects, AI, Analytics, Documents, Payments, Workflows, WebSocket, Search, Reports, Permissions, Integrations, Admin, LLM
- **Database**: PostgreSQL with SQLAlchemy ORM + Alembic migrations
- **Cache**: Redis for sessions, caching, and background tasks
- **AI Integration**: Ollama + OpenAI compatible LLM support
- **Security**: JWT authentication, RBAC, rate limiting, CORS protection
- **API Documentation**: Auto-generated OpenAPI/Swagger docs

### Frontend (React/TypeScript)
- **BI Dashboard**: Real-time analytics with charts, KPIs, and filters
- **E-Commerce Module**: Product catalog, cart, checkout, orders
- **MRP System**: BOM management, production planning, material requirements
- **POS System**: Point of sale, shift management, payment processing
- **Multi-language**: English, Myanmar, Chinese support

### Mobile App (React Native)
- **Cross-Platform**: iOS and Android support
- **Core Screens**: Dashboard, Contacts, Inventory, Invoices, Search, Profile
- **AI Copilot**: Integrated AI assistant
- **State Management**: Zustand store
- **Navigation**: React Navigation with type-safe routing

### Infrastructure
- **Docker**: Multi-stage builds for backend and frontend
- **Docker Compose**: Development and production configurations
- **Kubernetes**: Complete K8s manifests with Kustomize overlays (dev/staging/prod)
- **CI/CD**: GitHub Actions for CI, releases, security scanning (CodeQL, Snyk)
- **Monitoring**: Prometheus + Grafana dashboards
- **Backup**: Automated database backup scripts

### Security & Compliance
- Non-root container execution
- Environment-driven secrets management
- Network policies and RBAC
- Vulnerability scanning in CI pipeline
- Rate limiting and DDoS protection

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Git
- Node.js 18+ (for frontend development)
- Python 3.11+ (for backend development)

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd erp-system

# Copy environment configuration
cp .env.example .env
cp backend/.env.example backend/.env

# Edit .env files with your settings
# IMPORTANT: Change all SECRET_KEY and PASSWORD values!

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access services
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# pgAdmin: http://localhost:5050
# RedisInsight: http://localhost:8081
```

### Production Deployment

#### Option 1: Docker Compose
```bash
docker-compose -f docker-compose.prod.yml up -d
```

#### Option 2: Kubernetes
```bash
kubectl apply -k infra/k8s/overlays/production/
```

#### Option 3: Deploy Script
```bash
./deploy.sh <server-ip>
```

## 📁 Project Structure

```
erp-system/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── routers/        # API route handlers (19 modules)
│   │   ├── services/       # Business logic
│   │   ├── models.py       # Database models
│   │   ├── config.py       # Configuration management
│   │   └── main.py         # Application entry point
│   ├── alembic/            # Database migrations
│   ├── static/             # Static files (uploads, documents)
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile
├── frontend/               # React frontend
│   └── src/modules/
│       ├── bi-dashboard/   # Business Intelligence
│       ├── ecommerce/      # E-commerce module
│       ├── mrp/           # Material Requirements Planning
│       └── pos/           # Point of Sale
│   └── Dockerfile
├── mobile/                 # React Native app
│   ├── src/
│   │   ├── screens/       # App screens
│   │   ├── navigation/    # Navigation setup
│   │   ├── store/         # State management
│   │   └── utils/         # Utilities
│   └── package.json
├── infra/                  # Infrastructure as Code
│   └── k8s/               # Kubernetes manifests
│       ├── base/          # Base resources
│       └── overlays/      # Environment-specific configs
├── docker/                 # Docker configurations
│   ├── backups/           # Database backups
│   └── ssl/               # SSL certificates
├── scripts/                # Utility scripts
│   ├── deploy.sh          # Deployment automation
│   ├── backup.sh          # Database backups
│   └── health-check.sh    # Health monitoring
├── .github/workflows/      # CI/CD pipelines
├── .env.example            # Environment template
├── docker-compose.yml      # Development stack
├── docker-compose.prod.yml # Production stack
└── Makefile                # Development commands
```

## 🔧 Key Features

### Authentication & Authorization
- JWT-based authentication with refresh tokens
- Role-Based Access Control (RBAC)
- Permission-based resource access
- Session management with Redis

### Database
- PostgreSQL 15 with full-text search
- SQLAlchemy ORM with async support
- Alembic for schema migrations
- Automatic backup scheduling

### Caching & Queues
- Redis for caching and session storage
- Background task processing
- Rate limiting implementation

### AI Integration
- Ollama local LLM support
- OpenAI API compatibility
- AI-powered search and suggestions
- Automated content generation

### Monitoring & Observability
- Health check endpoints
- Prometheus metrics
- Structured logging
- Error tracking ready (Sentry)

## 🛡️ Security Best Practices

1. **Secrets Management**: All secrets via environment variables
2. **Container Security**: Non-root users, minimal base images
3. **Network Security**: Internal service isolation, CORS policies
4. **Rate Limiting**: Configurable per-endpoint limits
5. **Input Validation**: Pydantic models for all inputs
6. **Dependency Scanning**: Automated vulnerability checks

## 📊 API Endpoints

Base URL: `http://localhost:8000/api/v1`

| Module | Endpoints | Description |
|--------|-----------|-------------|
| Auth | `/auth/*` | Login, register, token refresh |
| CRM | `/crm/*` | Contacts, companies, deals |
| HR | `/hr/*` | Employees, attendance, payroll |
| Inventory | `/inventory/*` | Products, stock, warehouses |
| Finance | `/finance/*` | Invoices, payments, accounts |
| Projects | `/projects/*` | Tasks, timelines, teams |
| AI | `/ai/*` | LLM interactions, suggestions |
| Analytics | `/analytics/*` | Reports, dashboards, metrics |
| WebSocket | `/ws/*` | Real-time updates |

Full API documentation: `http://localhost:8000/docs`

## 🧪 Testing

```bash
# Run backend tests
cd backend
pytest

# Run frontend tests
cd frontend
npm test

# Run security scans
make scan-security
```

## 📝 Development Workflow

1. **Feature Branches**: Create from `master`
2. **Commits**: Follow Conventional Commits standard
3. **PRs**: Require review + CI passing
4. **Deployments**: Automated on merge to master

## 🔐 Environment Variables

See `.env.example` for complete list. Critical variables:

- `SECRET_KEY`: Cryptographic key (min 32 chars)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `JWT_SECRET_KEY`: JWT signing key
- `CORS_ORIGINS`: Allowed origins (comma-separated)

## 📚 Documentation

- [Architecture Decisions](docs/ARCHITECTURE_DECISIONS.md)
- [Database Migrations](docs/DATABASE_MIGRATIONS.md)
- [Production Deployment](docs/PRODUCTION_DEPLOYMENT.md)
- [API Summary](docs/API_SUMMARY.md)
- [Testing Guide](docs/TESTING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

- Issues: GitHub Issues
- Documentation: `/docs` folder
- API Docs: `http://localhost:8000/docs`

---

**Built with**: FastAPI, React, PostgreSQL, Redis, Docker, Kubernetes, GitHub Actions

**Version**: 1.0.0  
**Last Updated**: 2024
