# Auth Service

Authentication microservice for the Video Converter platform.

## Overview
Build status: All CI/CD workflows passing with GHCR_TOKEN PAT ✅

This service handles user registration, login, token verification, and authentication for the video processing pipeline.

## Features

- User registration and login
- JWT token generation and validation
- PostgreSQL persistence
- Redis session caching
- Prometheus metrics export (`/metrics`)

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r auth-service/requirements.txt

# Run the service
uvicorn auth-service.app.main:app --host 0.0.0.0 --port 8001

# Service will be available at http://localhost:8001
# API docs: http://localhost:8001/docs
# Health check: http://localhost:8001/health
# Metrics: http://localhost:8001/metrics
```

### Docker

```bash
# Build and run with docker-compose
docker-compose -f docker/docker-compose.yml up auth-service

# Build standalone image
docker build -f auth-service/Dockerfile -t auth-service:latest .

# Run standalone
docker run -p 8001:8001 \
  -e DATABASE_URL=postgresql://user:password@db:5432/videoconverter \
  -e REDIS_URL=redis://redis:6379 \
  -e SECRET_KEY=your-secret-key \
  auth-service:latest
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `REDIS_URL` | Redis connection string | ✅ |
| `SECRET_KEY` | JWT signing secret | ✅ |
| `WEBHOOK_URL` | Webhook notification endpoint | ❌ |

## API Endpoints

### Authentication

- `POST /auth/signup` - Register new user
- `POST /auth/login` - Login and get JWT token
- `POST /auth/verify` - Verify JWT token

### Health & Metrics

- `GET /health` - Health check endpoint (HTTP 200 if healthy)
- `GET /metrics` - Prometheus metrics in OpenMetrics format

## CI/CD Pipeline

### Continuous Integration

**Workflow**: `.github/workflows/auth-ci.yml`

Triggered on:
- Push to `auth-service/**`, `shared/**`, or `.github/workflows/auth-ci.yml`
- Pull requests targeting the same paths

**Jobs**:
1. **Lint** - Code style checks via flake8
2. **Security** - Vulnerability scanning (safety, bandit)
3. **Test** - Unit tests with pytest + PostgreSQL service

```bash
# Run locally
flake8 auth-service/ shared/
safety check -r auth-service/requirements.txt
bandit -r auth-service/ shared/
pytest tests/test_auth.py -v
```

### Docker Build & Push

**Workflow**: `.github/workflows/auth-docker.yml`

Triggered on:
- Push to `main` or `develop` branch
- Changes in `auth-service/**`, `shared/**`, or `.github/workflows/auth-docker.yml`

**Outputs**:
- Container image: `ghcr.io/<repository>/auth-service:<tag>`
- Tags: branch name, commit SHA, semantic version (if applicable)

**Registry**: GitHub Container Registry (ghcr.io)

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run auth tests
pytest tests/test_auth.py -v

# Run with coverage
pytest tests/test_auth.py --cov=auth-service --cov-report=html
```

## Monitoring

### Prometheus Metrics

The service exports Prometheus metrics at `GET /metrics`:

- **HTTP request metrics** (latency, status codes, request counts)
- **Python runtime metrics** (GC, memory, threads)
- **Custom application metrics** (available in future versions)

### Health Check

```bash
curl http://localhost:8001/health
# Response: {"status":"ok","service":"auth-service"}
```

## Docker Image

| Component | Details |
|-----------|---------|
| Base Image | `python:3.11-slim` |
| Dockerfile | `auth-service/Dockerfile` |
| Entry Point | `uvicorn app.main:app --host 0.0.0.0 --port 8001` |
| Port | 8001 |

## Troubleshooting

### Service fails to start

1. Verify environment variables are set:
   ```bash
   echo $DATABASE_URL $REDIS_URL $SECRET_KEY
   ```

2. Check database connectivity:
   ```bash
   psql $DATABASE_URL -c "SELECT 1"
   ```

3. Check logs:
   ```bash
   docker logs docker-auth-service-1  # Docker Compose
   ```

### Tests fail

1. Ensure PostgreSQL is running and accessible
2. Check database migrations
3. Review pytest output for specific errors

## Contributing

1. Create a feature branch from `develop`
2. Make changes in `auth-service/app/`
3. Update `auth-service/requirements.txt` if adding dependencies
4. Ensure CI passes (lint, security, tests)
5. Submit pull request

## License

Proprietary - Video Converter Project
