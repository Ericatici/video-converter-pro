# Video Service

Video processing microservice for the Video Converter platform. Handles video uploads, transcoding, and progress tracking.

## Overview

This service provides a REST API for uploading videos and a Celery worker for asynchronous video processing (encoding, transcoding, format conversion).

## Components

- **Video API** (`video-service/Dockerfile`) - FastAPI application serving REST endpoints
- **Video Worker** (`video-service/Dockerfile.worker`) - Celery worker for processing tasks
- **FFmpeg Integration** - Video encoding and transcoding

## Features

- Video upload via REST API
- Asynchronous processing with Celery + RabbitMQ
- FFmpeg-based transcoding
- Job status tracking
- Prometheus metrics export (`/metrics`)
- Progress webhooks (optional)

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r video-service/requirements.txt

# Run the API
uvicorn video-service.app.main:app --host 0.0.0.0 --port 8002

# Run the worker (in separate terminal)
celery -A video-service.app.celery_app worker --loglevel=info

# Service will be available at http://localhost:8002
# API docs: http://localhost:8002/docs
# Health check: http://localhost:8002/health
# Metrics: http://localhost:8002/metrics
```

### Docker Compose

```bash
# Start video service API + worker
docker-compose -f docker/docker-compose.yml up video-service video-worker

# Both services share the same image but use different entry points
```

### Standalone Docker Build

```bash
# Build API image
docker build -f video-service/Dockerfile -t video-service:latest .

# Build worker image
docker build -f video-service/Dockerfile.worker -t video-worker:latest .

# Run API
docker run -p 8002:8002 \
  -e DATABASE_URL=postgresql://user:password@db:5432/videoconverter \
  -e RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/ \
  -e SECRET_KEY=your-secret-key \
  video-service:latest

# Run worker
docker run \
  -e DATABASE_URL=postgresql://user:password@db:5432/videoconverter \
  -e RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/ \
  -e SECRET_KEY=your-secret-key \
  -v uploads:/app/uploads \
  -v processed:/app/processed \
  video-worker:latest
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `RABBITMQ_URL` | RabbitMQ broker URL | ✅ |
| `REDIS_URL` | Redis connection string (caching) | ✅ |
| `SECRET_KEY` | JWT signing secret | ✅ |
| `WEBHOOK_URL` | Webhook notification endpoint | ❌ |

## API Endpoints

### Video Management

- `POST /videos/upload` - Upload and queue video for processing
- `GET /videos/status/<video_id>` - Get processing status
- `GET /videos/download/<video_id>` - Download processed video

### Health & Metrics

- `GET /health` - Health check endpoint (HTTP 200 if healthy)
- `GET /metrics` - Prometheus metrics in OpenMetrics format

## CI/CD Pipeline

### Continuous Integration

**Workflow**: `.github/workflows/video-ci.yml`

Triggered on:
- Push to `video-service/**`, `shared/**`, or `.github/workflows/video-ci.yml`
- Pull requests targeting the same paths

**Jobs**:
1. **Lint** - Code style checks via flake8
2. **Security** - Vulnerability scanning (safety, bandit)
3. **Test** - Integration tests with PostgreSQL, Redis, RabbitMQ services

**Services used in tests**:
- PostgreSQL 15 (database)
- Redis 7 (caching)
- RabbitMQ 3.13 (message broker)

```bash
# Run locally
flake8 video-service/ shared/
safety check -r video-service/requirements.txt
bandit -r video-service/ shared/
pytest tests/test_videos.py -v
```

### Docker Build & Push

**Workflow**: `.github/workflows/video-docker.yml`

Triggered on:
- Push to `main` or `develop` branch
- Changes in `video-service/**`, `shared/**`, or `.github/workflows/video-docker.yml`

**Dual builds**:
1. **Video API** - Container image: `ghcr.io/<repository>/video-service:<tag>`
2. **Celery Worker** - Container image: `ghcr.io/<repository>/video-service/worker:<tag>`

**Tags**: branch name, commit SHA, semantic version (if applicable)

**Registry**: GitHub Container Registry (ghcr.io)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Video Service API (FastAPI on port 8002)               │
├─────────────────────────────────────────────────────────┤
│ POST /videos/upload    → Enqueues task to RabbitMQ      │
│ GET /videos/status     → Queries database for status    │
│ GET /videos/download   → Returns processed file         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  RabbitMQ Broker     │ (amqp://...)
              └──────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Celery Worker (Long-running background process)        │
├─────────────────────────────────────────────────────────┤
│ 1. Dequeue task from RabbitMQ                          │
│ 2. Download video from uploads/                         │
│ 3. Run FFmpeg transcoding                              │
│ 4. Save result to processed/                            │
│ 5. Update database with completion status              │
│ 6. (Optional) Send webhook notification                │
└─────────────────────────────────────────────────────────┘
```

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run video tests
pytest tests/test_videos.py -v

# Run with coverage
pytest tests/test_videos.py --cov=video_service --cov-report=html
```

## Monitoring

### Prometheus Metrics

The API exports Prometheus metrics at `GET /metrics`:

- **HTTP request metrics** (latency, status codes, request counts)
- **Celery task metrics** (task count, duration, success/failure)
- **Worker metrics** (worker alive status, heartbeat timestamp)
- **Python runtime metrics** (GC, memory, threads)

### Health Check

```bash
curl http://localhost:8002/health
# Response: {"status":"ok","service":"video-service"}
```

## File Structure

```
video-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── routes.py            # API endpoints
│   ├── celery_app.py        # Celery task & metrics config
│   └── processor.py         # FFmpeg video processing logic
├── Dockerfile               # API image definition
├── Dockerfile.worker        # Worker image definition
└── requirements.txt         # Python dependencies
```

## Docker Images

| Component | Dockerfile | Base Image | Entry Point |
|-----------|-----------|-----------|-------------|
| **API** | `Dockerfile` | `python:3.11-slim` | `uvicorn app.main:app --port 8002` |
| **Worker** | `Dockerfile.worker` | `python:3.11-slim` | `celery -A app.celery_app worker` |

Both include FFmpeg for video processing.

## Troubleshooting

### API starts but worker doesn't process tasks

1. Check RabbitMQ is running:
   ```bash
   docker ps | grep rabbitmq
   ```

2. Verify worker can connect to broker:
   ```bash
   docker logs docker-video-worker-1
   ```

3. Check Celery logs for connection errors

### Video upload succeeds but processing never completes

1. Verify worker is running
2. Check RabbitMQ queue depth:
   ```bash
   curl http://localhost:15672/api/queues (RabbitMQ management UI)
   ```

3. Review FFmpeg availability:
   ```bash
   docker exec docker-video-worker-1 which ffmpeg
   ```

### Tests fail

1. Ensure all services running (PostgreSQL, Redis, RabbitMQ)
2. Check database connectivity
3. Review pytest output for specific errors

## Contributing

1. Create a feature branch from `develop`
2. Make changes in `video-service/app/`
3. Update `video-service/requirements.txt` if adding dependencies
4. Ensure CI passes (lint, security, tests)
5. Submit pull request

## License

Proprietary - Video Converter Project
