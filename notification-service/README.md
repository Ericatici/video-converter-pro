# Notification Service

Event listener and notification microservice for the Video Converter platform. Consumes RabbitMQ events and sends notifications (webhooks, emails, etc.).

## Overview

This service listens to events published by other microservices (video completion, errors, etc.) and sends notifications via webhooks or email.

## Features

- RabbitMQ event listener (async event consumer)
- Webhook notifications
- Email notifications (via SMTP)
- Event routing and filtering
- PostgreSQL event persistence
- Prometheus metrics export (`/metrics`)

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r notification-service/requirements.txt

# Start the service (event listener)
python -m notification-service.app.listeners

# Alternative: Run via uvicorn for FastAPI health/metrics endpoints
uvicorn notification-service.app.main:app --host 0.0.0.0 --port 8003
```

### Docker Compose

```bash
# Start notification service
docker-compose -f docker/docker-compose.yml up notification-service

# Service runs as background listener; no HTTP port exposed by default
```

### Standalone Docker Build

```bash
# Build image
docker build -f notification-service/Dockerfile -t notification-service:latest .

# Run listener
docker run \
  -e DATABASE_URL=postgresql://user:password@db:5432/videoconverter \
  -e RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/ \
  -e SECRET_KEY=your-secret-key \
  notification-service:latest
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `RABBITMQ_URL` | RabbitMQ broker URL | ✅ |
| `REDIS_URL` | Redis connection string (caching) | ❌ |
| `SECRET_KEY` | JWT signing secret | ✅ |
| `SMTP_HOST` | Email SMTP server | ❌ |
| `SMTP_PORT` | SMTP server port | ❌ |
| `SMTP_USER` | SMTP authentication user | ❌ |
| `SMTP_PASSWORD` | SMTP authentication password | ❌ |
| `SMTP_FROM` | Sender email address | ❌ |

## API Endpoints

### Health & Metrics

- `GET /health` - Health check endpoint (HTTP 200 if healthy)
- `GET /metrics` - Prometheus metrics in OpenMetrics format

### Webhook Routes (optional)

- `POST /webhook/video-complete` - Receive video completion events
- `POST /webhook/error` - Receive error notifications

## Event Handling

### Subscribed Events (RabbitMQ)

The service listens to events on RabbitMQ:

- `video.uploaded` - New video uploaded
- `video.processing_start` - Video processing started
- `video.processing_complete` - Video processing completed
- `video.error` - Processing error occurred

**Routing Key Pattern**: `video.*`

### Actions

When events are received:
1. Persist event to database for audit trail
2. Check notification preferences/rules
3. Send webhook to registered endpoint (if configured)
4. Send email notification (if SMTP configured)
5. Update event status

## CI/CD Pipeline

### Continuous Integration

**Workflow**: `.github/workflows/notification-ci.yml`

Triggered on:
- Push to `notification-service/**`, `shared/**`, or `.github/workflows/notification-ci.yml`
- Pull requests targeting the same paths

**Jobs**:
1. **Lint** - Code style checks via flake8
2. **Security** - Vulnerability scanning (safety, bandit)
3. **Test** - Placeholder tests (to be implemented)

**Services used in tests**:
- PostgreSQL 15 (database)
- RabbitMQ 3.13 (message broker)

```bash
# Run locally
flake8 notification-service/ shared/
safety check -r notification-service/requirements.txt
bandit -r notification-service/ shared/
pytest tests/test_notification.py -v
```

### Docker Build & Push

**Workflow**: `.github/workflows/notification-docker.yml`

Triggered on:
- Push to `main` or `develop` branch
- Changes in `notification-service/**`, `shared/**`, or `.github/workflows/notification-docker.yml`

**Outputs**:
- Container image: `ghcr.io/<repository>/notification-service:<tag>`
- Tags: branch name, commit SHA, semantic version (if applicable)

**Registry**: GitHub Container Registry (ghcr.io)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ RabbitMQ Broker                                         │
│ Exchange: video-events (topic)                          │
│ Routing Key: video.*                                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Notification Service Listener (Event Consumer)         │
├─────────────────────────────────────────────────────────┤
│ 1. Listen on RabbitMQ queue (video.notifications)      │
│ 2. Deserialize event message                           │
│ 3. Save to database (audit trail)                      │
│ 4. Check notification rules/preferences                │
│ 5. Route to handlers (webhook, email, etc.)            │
│ 6. Retry on failure                                    │
└─────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐          ┌─────────┐          ┌─────────┐
    │ Webhook │          │  Email  │          │ Database│
    │ Endpoint│          │  SMTP   │          │  Log    │
    └─────────┘          └─────────┘          └─────────┘
```

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run notification tests (placeholder)
pytest tests/test_notification.py -v

# Add tests in tests/test_notification.py when ready
```

## Monitoring

### Prometheus Metrics

The service exports Prometheus metrics at `GET /metrics`:

- **Event processing metrics** (events received, processed, failed)
- **Notification delivery metrics** (webhooks sent, emails sent, retry attempts)
- **Python runtime metrics** (GC, memory, threads)

### Health Check

```bash
curl http://localhost:8003/health
# Response: {"status":"ok","service":"notification-service"}
```

## File Structure

```
notification-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application (health/metrics)
│   ├── routes.py            # Optional webhook routes
│   ├── listeners.py         # RabbitMQ event listener
│   └── webhook.py           # Webhook notification handler
├── Dockerfile               # Container definition
└── requirements.txt         # Python dependencies
```

## Docker Image

| Component | Dockerfile | Base Image | Entry Point |
|-----------|-----------|-----------|-------------|
| **Listener** | `Dockerfile` | `python:3.11-slim` | `python -m app.listeners` |

## Troubleshooting

### Service doesn't start

1. Check RabbitMQ is running and accessible:
   ```bash
   docker ps | grep rabbitmq
   ```

2. Verify connection string:
   ```bash
   docker logs docker-notification-service-1
   ```

### Events not being processed

1. Check RabbitMQ queue:
   ```bash
   docker logs docker-rabbitmq-1 | grep queue
   ```

2. Verify service is listening:
   ```bash
   docker logs docker-notification-service-1 | grep "Listening"
   ```

### Webhook delivery failures

1. Verify webhook endpoint is accessible
2. Check network connectivity from notification service
3. Review retry logic in webhook handler

## Contributing

1. Create a feature branch from `develop`
2. Make changes in `notification-service/app/`
3. Update `notification-service/requirements.txt` if adding dependencies
4. Add or update tests in `tests/test_notification.py`
5. Ensure CI passes (lint, security, tests)
6. Submit pull request

## License

Proprietary - Video Converter Project
