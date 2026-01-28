# Microservices Quick Reference

## Project Structure After Transformation

```
video-converter-prod/
├── auth-service/              # User authentication (port 8001)
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   └── routes.py         # /auth endpoints
│   ├── Dockerfile
│   └── requirements.txt
│
├── video-service/             # Video processing (port 8002)
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── routes.py         # /videos endpoints
│   │   ├── processor.py      # FFmpeg + event publishing
│   │   └── celery_app.py     # Async task config
│   ├── Dockerfile
│   ├── Dockerfile.worker     # Celery worker
│   └── requirements.txt
│
├── notification-service/      # Webhook notifications
│   ├── app/
│   │   ├── main.py           # Health endpoint
│   │   ├── webhook.py        # Webhook sending logic
│   │   └── listeners.py      # RabbitMQ event consumer
│   ├── Dockerfile
│   └── requirements.txt
│
├── shared/                    # Shared code (all services use this)
│   ├── config.py             # Settings from .env
│   ├── database.py           # SQLAlchemy session
│   ├── models.py             # User, Video models
│   └── auth_utils.py         # JWT & password functions
│
├── docker/
│   └── docker-compose.yml    # 7 containers orchestration
│
├── README.md                 # Full documentation
└── MIGRATION.md              # Before/after comparison
```

## Key Improvements

| Feature | Monolith | Microservices |
|---------|----------|----------------|
| **Video Upload** | Blocks while processing | Returns immediately (queued) |
| **Scalability** | Single process | Independent workers |
| **Failure Isolation** | One crash = all down | Service crash isolated |
| **Webhook Failures** | Blocks upload | Retries in background |
| **Development** | All in one file | Separate codebases |
| **Deployment** | 1 container | 6+ containers |

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| Auth Service | 8001 | http://localhost:8001 |
| Video Service | 8002 | http://localhost:8002 |
| PostgreSQL | 5432 | postgresql://db:5432 |
| RabbitMQ | 5672 | amqp://rabbitmq:5672 |
| RabbitMQ UI | 15672 | http://localhost:15672 |
| Redis | 6379 | redis://redis:6379 |

## Communication Patterns

### Synchronous (Request/Response)
```
Client → Auth Service ✓ Immediate response
Client → Video Service → Auth Service (token verify)
```

### Asynchronous (Event-Driven)
```
Video Service → [FFmpeg conversion] → RabbitMQ (event)
                                        ↓
                    Notification Service (listens & sends webhook)
```

## How Video Processing Works Now

1. Client uploads video → Video Service API (port 8002)
2. API stores file, creates DB record, **queues Celery task**
3. API returns `{"status": "queued"}` immediately ✓
4. Celery Worker processes video in background
5. After conversion, Worker publishes event to RabbitMQ
8. Notification Service receives event → sends webhook notification
7. User can download when status = "completed"

## Docker Compose Commands

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# View logs for specific service
docker-compose -f docker/docker-compose.yml logs -f video-service

# Stop all services
docker-compose -f docker/docker-compose.yml down

# Rebuild images
docker-compose -f docker/docker-compose.yml build --no-cache

# View running containers
docker-compose -f docker/docker-compose.yml ps
```

## Environment Setup

Create `.env` file:
```env
DATABASE_URL=postgresql://user:password@db:5432/videoconverter
REDIS_URL=redis://redis:6379
SECRET_KEY=your-secret-key-change-in-production
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

## Important Changes from Monolith

### 1. **API Endpoints Changed**
```
Before: http://localhost:8000/*
After:  http://localhost:8001/auth/* (Auth Service)
        http://localhost:8002/videos/* (Video Service)
```

### 2. **Async Video Processing**
```
Before: POST /videos/upload → waits for FFmpeg → slow response
After:  POST /videos/upload → queues task → fast response
```

### 3. **No Direct Email Blocking**
```
Before: Processor sends email synchronously
After:  Worker publishes event → Notification Service sends async
```

### 4. **Services Are Independent**
```
Before: All code in one app
After:  Each service has own codebase, requirements, Dockerfile
```

## Common Tasks

### Check if services are running
```bash
curl http://localhost:8001/health  # Auth
curl http://localhost:8002/health  # Video
```

### View RabbitMQ events
```bash
# GUI: http://localhost:15672 (guest/guest)
# Or list queues:
docker exec rabbitmq rabbitmqctl list_queues
```

### View database
```bash
psql -h localhost -U user -d videoconverter
# Tables: users, videos
```

### View Celery tasks
```bash
docker logs video-worker  # Shows task processing
```

## Troubleshooting

**Services can't find each other?**
- Check all containers are on `microservices` network
- Use service name as hostname (not localhost)

**Video not processing?**
- Check video-worker logs: `docker logs video-worker`
- Verify RabbitMQ: `docker exec rabbitmq rabbitmqctl status`

**Webhook not receiving notifications?**
- Check notification-service logs
- Verify WEBHOOK_URL in .env points to your server
- Test webhook: `curl http://localhost:3000/health`

## Next: Add API Gateway

To simplify client URLs, add Nginx/Kong in front:
```
Client → API Gateway (8000) → Routes to services
```

Then client only uses: `http://localhost:8000/auth/*` and `http://localhost:8000/videos/*`

See MIGRATION.md for phase-by-phase roadmap.
