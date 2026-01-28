# Microservices Migration Guide

This document explains the transformation from monolith to microservices architecture.

## Changes Made

### 1. **Directory Structure**
- **Before**: Single `app/` directory with all modules mixed
- **After**: Separate service directories (auth-service, video-service, notification-service) + shared code

### 2. **Shared Code** (`shared/`)
Common code extracted to be reused across services:
- `config.py` - Environment settings (moved from app/)
- `database.py` - SQLAlchemy setup (moved from app/)
- `models.py` - Database models (User, Video) - now centralized
- `auth_utils.py` - JWT utilities (extracted from auth/utils.py)

### 3. **Auth Service** (Independent)
- Runs on port **8001**
- Handles user authentication only
- Provides `/auth/verify` endpoint for other services to validate tokens
- **No dependencies** on video or notification services

### 4. **Video Service** (Async Processing)
- Runs on port **8002**
- **Key Changes**:
  - Upload now queues async task instead of blocking
  - Response immediately: `{"video_id": video_id, "status": "queued"}`
  - Celery processes videos in background
  - **Publishes events** to RabbitMQ after processing

### 5. **Notification Service** (Event-Driven)
- Runs independently (no HTTP port in production)
- **Key Changes**:
  - No longer called synchronously by processor
  - Listens to RabbitMQ events: `video.completed`, `video.error`
  - Decoupled from video service - can fail without blocking uploads
  - Can be scaled independently

### 6. **Asynchronous Processing**
- **Before**: FFmpeg blocking in request handler
- **After**: 
  - Celery worker processes in background
  - RabbitMQ publishes events
  - Notification service consumes events

### 7. **Inter-Service Communication**
- **Auth ↔ Video**: JWT tokens verified locally (sync)
- **Video ↔ Notification**: RabbitMQ events (async)
- **Services can run on different machines**

## Database Changes

**Schema remains the same**, but now:
- Shared by all services (can be split later)
- Each service imports models from `shared/models.py`
- No circular dependencies

## Environment Variables

Added new variables for microservices:
```env
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
SECRET_KEY=your-secret-key
```

## Deployment

### Container Structure
```
docker-compose.yml
├── db (PostgreSQL)
├── rabbitmq (Message broker)
├── redis (Cache)
├── auth-service (FastAPI API)
├── video-service (FastAPI API)
├── video-worker (Celery worker)
└── notification-service (Event listener)
```

### Network Isolation
- All services on same `microservices` network
- Services communicate via hostnames: `auth-service:8001`, `rabbitmq:5672`
- No external service-to-service communication

## API Compatibility

### Before (Monolith)
```
POST http://localhost:8000/auth/signup
POST http://localhost:8000/auth/login
POST http://localhost:8000/videos/upload
GET  http://localhost:8000/videos/status
GET  http://localhost:8000/videos/download/1
```

### After (Microservices)
```
POST http://localhost:8001/auth/signup       (Auth Service)
POST http://localhost:8001/auth/login        (Auth Service)
POST http://localhost:8002/videos/upload     (Video Service)
GET  http://localhost:8002/videos/status     (Video Service)
GET  http://localhost:8002/videos/download/1 (Video Service)
```

**Note**: Clients must now know service URLs. Future: Add API Gateway for unified endpoint.

## Performance Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Video Upload Latency** | Blocking (depends on file size) | Immediate (async queued) |
| **Service Isolation** | One crash = everything down | One service failure isolated |
| **Scaling** | Scale entire app | Scale individual services |
| **Email Failures** | Block video completion | Silent (retry in background) |
| **Resource Usage** | Single process | Distributed across workers |

## Rollback Plan

If needed to revert to monolith:
1. Merge code from services back to `app/`
2. Remove Celery/RabbitMQ dependencies
3. Convert async processors back to sync calls
4. Revert docker-compose to single app container

## Next Steps (Recommended)

### Phase 1: Add API Gateway (1-2 weeks)
- Nginx/Kong as single entry point
- Route requests to services
- Add rate limiting

### Phase 2: Add Monitoring (2-3 weeks)
- Prometheus for metrics
- Grafana for dashboards
- ELK for centralized logging

### Phase 3: Kubernetes Deployment (3-4 weeks)
- Helm charts for each service
- Service discovery
- Auto-scaling

### Phase 4: Database Isolation (4-6 weeks)
- Separate databases per service
- Event sourcing pattern
- Data consistency strategy

## Troubleshooting

### Services can't communicate
- Check network: `docker network ls`
- Check DNS resolution: `docker exec <container> ping <service-name>`
- Verify docker-compose network matches in config

### RabbitMQ events not being processed
- Check rabbitmq is running: `docker ps | grep rabbitmq`
- Check exchange/queue: `docker exec rabbitmq rabbitmqctl list_queues`
- Check listener logs: `docker logs notification-service`

### Video processing not starting
- Check celery worker: `docker logs video-worker`
- Check broker connection: Verify RABBITMQ_URL
- Check for tasks: `docker exec rabbitmq rabbitmqctl list_queues`

## Questions?

Refer to README.md for API documentation and service details.
