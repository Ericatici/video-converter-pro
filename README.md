# Video Converter - Microservices Architecture

This project has been transformed from a monolithic MVP into a scalable microservices architecture.

**CI/CD Status:** All tests pass through pull request validation before merging to main ✅

## Project Structure

```
├── auth-service/           # Authentication & User Management Service
│   ├── app/
│   │   ├── main.py        # FastAPI app entry point (port 8001)
│   │   └── routes.py      # Auth endpoints (signup, login, verify)
│   ├── Dockerfile
│   └── requirements.txt
│
├── video-service/          # Video Upload & Processing Service
│   ├── app/
│   │   ├── main.py        # FastAPI app entry point (port 8002)
│   │   ├── routes.py      # Video endpoints (upload, status, download)
│   │   ├── processor.py   # FFmpeg conversion & event publishing
│   │   └── celery_app.py  # Async task configuration
│   ├── Dockerfile         # API container
│   ├── Dockerfile.worker  # Celery worker container
│   └── requirements.txt
│
├── notification-service/   # Event-driven Webhook Notification Service
│   ├── app/
│   │   ├── main.py        # FastAPI health check endpoint
│   │   ├── webhook.py     # HTTP webhook delivery logic
│   │   └── listeners.py   # RabbitMQ event consumer
│   ├── Dockerfile
│   └── requirements.txt
│
├── shared/                 # Shared Code (Models, Config, Utilities)
│   ├── config.py          # Settings & environment variables
│   ├── database.py        # SQLAlchemy setup & session management
│   ├── models.py          # Shared DB models (User, Video)
│   ├── redis_client.py    # Redis singleton client & cache helpers
│   └── auth_utils.py      # JWT & password utilities
│
├── docker/
│   └── docker-compose.yml # Multi-container orchestration
│
├── tests/                  # Test files
├── uploads/                # Uploaded video files (volume)
├── processed/              # Processed video files (volume)
└── README.md
```

## Services Overview

### 1. **Auth Service** (Port 8001)
- **Purpose**: User authentication & authorization
- **Endpoints**:
  - `POST /auth/signup` - Create user account
  - `POST /auth/login` - Authenticate & get JWT token
  - `POST /auth/verify` - Verify token (used by other services)
- **Database**: PostgreSQL (shared)
- **Responsibilities**: User management, password hashing, JWT token generation

### 2. **Video Service** (Port 8002)
- **Purpose**: Video upload & processing orchestration
- **Endpoints**:
  - `POST /videos/upload` - Upload video or ZIP file (queues async task, invalidates cache)
  - `GET /videos/status` - List user's videos (cached with 120s TTL via Redis)
  - `GET /videos/download/{id}` - Download processed video
- **Database**: PostgreSQL (shared)
- **Cache**: Redis (query results cached with 120s TTL)
- **Message Queue**: RabbitMQ (publishes video events)
- **Worker**: Celery worker process (runs async video conversion)
- **ZIP Upload Support**: Accepts ZIP files, extracts and validates video files (.mp4, .mov, .mkv, .avi, .webm)
- **Responsibilities**: File management, task scheduling, status tracking, cache management

### 3. **Notification Service**
- **Purpose**: Event-driven webhook notifications
- **Message Queue**: RabbitMQ (consumes video events)
- **Database**: PostgreSQL (shared - user lookup)
- **Events Listened**:
  - `video.completed` - Send webhook notification with download URL
  - `video.error` - Send webhook notification with error details
- **Webhook Delivery**: HTTP POST to configured webhook URL with event payload
- **Responsibilities**: Webhook notifications, event consumption, external integrations

### 4. **Video Worker** (Celery Task Queue)
- **Purpose**: Async video processing
- **Framework**: Celery 5.3.4 with RabbitMQ broker
- **Processing Flow**:
  1. Receives video conversion task from Video Service
  2. Uses FFmpeg to convert video format
  3. Updates video status in PostgreSQL
  4. Publishes `video.completed` or `video.error` event to RabbitMQ
  5. Invalidates Redis cache for user's video status
- **Responsibilities**: Video codec conversion, error handling, status updates

## Infrastructure

### Data Flow

```
Client → Auth Service ──┐
         ↓              │
    JWT Token          │
         ↓              ↓
Client → Video Service (API)
         ├→ Upload file (extract from ZIP if needed)
         ├→ Create DB record
         ├→ Invalidate Redis cache
         └→ Queue Celery task
              ↓
         Video Worker (Celery)
              ├→ FFmpeg conversion
              ├→ Update DB status
              ├→ Invalidate Redis cache
              └→ Publish event to RabbitMQ
                         ↓
         Notification Service (Listener)
              ├→ Receives event
              ├→ Query DB for user
              └→ Send HTTP webhook notification
              
GET /videos/status (GET requests cached in Redis with 120s TTL)
         ├→ Check Redis cache first
         ├→ Query PostgreSQL if cache miss
         └→ Store result in Redis for 120 seconds
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | FastAPI 0.104.1 | Web services |
| **Server** | Uvicorn (ASGI) | ASGI server |
| **ORM** | SQLAlchemy 2.0.23 | Database abstraction |
| **Database** | PostgreSQL 15 | Persistent data store |
| **Cache Layer** | Redis 7 | Query result caching (120s TTL) |
| **Message Queue** | RabbitMQ 3.13 | Event-driven communication |
| **Task Queue** | Celery 5.3.4 | Async video processing |
| **Video Processing** | FFmpeg | Video codec conversion |
| **Auth** | JWT (python-jose) | Token-based authentication |
| **Notifications** | Webhooks (HTTP POST) | Event notifications |
| **Config Mgmt** | Pydantic 2.x + pydantic-settings | Environment variables & settings |
| **Testing** | Pytest + httpx 0.25.1 | Integration testing |

## Getting Started

### Prerequisites
- Docker & Docker Compose installed
- PostgreSQL connection (via compose)
- RabbitMQ running (via compose)

### Environment Variables

Environment variables are configured in [docker/docker-compose.yml](docker/docker-compose.yml):

```env
# Database
DATABASE_URL=postgresql://user:password@db:5432/videoconverter

# Redis (Query caching)
REDIS_URL=redis://redis:6379

# Security
SECRET_KEY=your-secret-key-change-in-production

# Webhook for Notifications
WEBHOOK_URL=http://localhost:3001/webhook

# RabbitMQ (Message broker)
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
```

### Running with Docker Compose

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# (Optional) Run webhook test server locally to receive notifications
python webhook_test_server.py

# Stop services
docker-compose -f docker/docker-compose.yml down
```

### Optional: Database bootstrap script
- Script: `docker/db_init.sql`
- Purpose: creates `users` and `videos` tables matching `shared/models.py` (indices included)
- Run inside the compose Postgres:
  - `docker-compose -f docker/docker-compose.yml exec -T db psql -U user -d videoconverter -f /docker/db_init.sql`
- Or from host (with psql installed):
  - `psql -h localhost -p 5432 -U user -d videoconverter -f docker/db_init.sql`
> Note: Services already create tables via SQLAlchemy on startup; this script is optional.

### Service Startup Order
1. **PostgreSQL** - Database initialization (5432)
2. **RabbitMQ** - Message broker startup (5672, management UI at 15672)
3. **Redis** - Cache layer (6379)
4. **Auth Service** - API startup (8001)
5. **Video Service** - API startup (8002)
6. **Video Worker** - Celery worker startup
7. **Notification Service** - Event listener startup

## API Usage

curl http://localhost:8001/health  # Auth Service
curl http://localhost:8002/health  # Video Service

curl http://localhost:8001/docs  # Auth Service
curl http://localhost:8002/docs  # Video Service

### 1. Create User Account
```bash
curl -X POST http://localhost:8001/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'
```

### 2. Login
```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'
```

### 3. Upload Video (Plain File)
```bash
TOKEN="your-jwt-token-here"

curl -X POST http://localhost:8002/videos/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@video.mp4"
```

### 3b. Upload Video (ZIP File)
```bash
TOKEN="your-jwt-token-here"

# ZIP file containing video.mp4
curl -X POST http://localhost:8002/videos/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@videos.zip"

# Supported formats in ZIP: .mp4, .mov, .mkv, .avi, .webm
```

### 4. Check Status
```bash
curl -X GET http://localhost:8002/videos/status \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Download Processed Video
```bash
curl -X GET http://localhost:8002/videos/download/1 \
  -H "Authorization: Bearer $TOKEN" \
  -o processed_video.zip
```

## Caching Strategy

### Redis Query Caching
The `GET /videos/status` endpoint uses Redis caching to improve performance:

**Cache Configuration:**
- **TTL**: 120 seconds (2 minutes)
- **Cache Key**: `video_status:{username}`
- **Cache Location**: Redis (deployed via Docker Compose on port 6379)

**Cache Behavior:**
1. **Cache Hit**: Returns cached status from Redis (instant response)
2. **Cache Miss**: Queries PostgreSQL, stores result in Redis with 120s TTL
3. **Cache Invalidation**: Automatically invalidated when:
   - User uploads a new video
   - Video processing completes (status changed to "completed")
   - Video processing fails (status changed to "error")

**Performance Impact:**
- First request: ~50-100ms (database query)
- Subsequent requests (within 120s): <5ms (Redis cache)

### Cache Helpers (shared/redis_client.py)
- `get_redis_client()` - Singleton Redis client factory
- `_get_cached_status(username)` - Retrieve cached status
- `_set_cached_status(username, data)` - Store status with TTL
- `_invalidate_status_cache(username)` - Clear cache entry

## Webhook Notifications

### Configuration
Set the webhook URL in your environment:
```env
WEBHOOK_URL=https://your-webhook-receiver.com/webhooks/videos
```

### Webhook Payloads

**Video Completed Event:**
```json
{
  "event": "video.completed",
  "video_id": 123,
  "username": "john_doe",
  "timestamp": "2026-01-16T10:30:00Z",
  "download_url": "http://localhost:8002/videos/download/123"
}
```

**Video Error Event:**
```json
{
  "event": "video.error",
  "video_id": 123,
  "username": "john_doe",
  "timestamp": "2026-01-16T10:30:00Z",
  "error": "Unsupported video format"
}
```

### Testing Webhooks Locally
```bash
# Run webhook test server (listens on port 3001)
python webhook_test_server.py

# Configure WEBHOOK_URL
WEBHOOK_URL=http://localhost:3001/webhook
```

## Testing

Run tests from the project root:
```bash
pytest tests/ -v
```

**Test Results: 18/18 PASSING ✅**
- **Auth Service Tests**: 7/7 passing
  - Health check, user signup, duplicate user detection, login, invalid credentials, token verification
- **Video Service Tests**: 11/11 passing
  - Health check, video upload (plain & ZIP), status tracking (empty & after upload), cache consistency
  - ZIP file extraction, unsupported format handling, authentication requirements

## Development

### Local Setup (Without Docker)

1. **Install Python 3.11+** and dependencies:
```bash
pip install -r shared/requirements.txt
pip install -r auth-service/requirements.txt
pip install -r video-service/requirements.txt
pip install -r notification-service/requirements.txt
```

2. **Run individual services**:

Auth Service:
```bash
cd auth-service
python -m uvicorn app.main:app --reload --port 8001
```

Video Service:
```bash
cd video-service
python -m uvicorn app.main:app --reload --port 8002
```

Celery Worker:
```bash
cd video-service
celery -A app.celery_app worker --loglevel=info
```

Notification Service:
```bash
cd notification-service
python -m app.listeners
```

## Testing

Run tests from the project root:
```bash
pytest tests/ -v
```

## Continuous Integration & Deployment

This project uses **separate CI/CD pipelines** for each microservice, allowing independent development and deployment.

### CI/CD Architecture

Each service has its own:
- **CI Pipeline**: Lint, security scan, and tests
- **Docker Build Pipeline**: Build and push to ghcr.io
- **Path Filters**: Only runs when service code changes

### Service Pipelines

#### **Auth Service**
- **CI Workflow**: `.github/workflows/auth-ci.yml`
- **Docker Workflow**: `.github/workflows/auth-docker.yml`
- **Triggers**: Changes to `auth-service/` or `shared/`
- **Image**: `ghcr.io/YOUR_USERNAME/video-converter-auth`
- **Badge**: ![Auth CI](https://github.com/YOUR_USERNAME/video-converter-prod/actions/workflows/auth-ci.yml/badge.svg)

#### **Video Service**
- **CI Workflow**: `.github/workflows/video-ci.yml`
- **Docker Workflow**: `.github/workflows/video-docker.yml`
- **Triggers**: Changes to `video-service/` or `shared/`
- **Images**: 
  - API: `ghcr.io/YOUR_USERNAME/video-converter-video`
  - Worker: `ghcr.io/YOUR_USERNAME/video-converter-worker`
- **Badge**: ![Video CI](https://github.com/YOUR_USERNAME/video-converter-prod/actions/workflows/video-ci.yml/badge.svg)

#### **Notification Service**
- **CI Workflow**: `.github/workflows/notification-ci.yml`
- **Docker Workflow**: `.github/workflows/notification-docker.yml`
- **Triggers**: Changes to `notification-service/` or `shared/`
- **Image**: `ghcr.io/YOUR_USERNAME/video-converter-notification`
- **Badge**: ![Notification CI](https://github.com/YOUR_USERNAME/video-converter-prod/actions/workflows/notification-ci.yml/badge.svg)

### Pipeline Flow

```
┌─────────────────────────────────────────────────┐
│  Developer pushes code to auth-service/         │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  Auth CI Pipeline Triggered                     │
│  ├─ Lint (flake8)                               │
│  ├─ Security Scan (safety, bandit)              │
│  └─ Tests (pytest)                              │
└────────────────┬────────────────────────────────┘
                 │
                 ▼ (if on main/develop)
┌─────────────────────────────────────────────────┐
│  Auth Docker Pipeline Triggered                 │
│  ├─ Build image                                 │
│  ├─ Tag (latest, main, main-abc123)             │
│  └─ Push to ghcr.io                             │
└─────────────────────────────────────────────────┘
```

### Path Filter Behavior

**Example 1**: Change `auth-service/app/routes.py`
- ✅ Triggers: `auth-ci.yml`, `auth-docker.yml` (on main/develop)
- ❌ Skips: video-ci, notification-ci

**Example 2**: Change `shared/database.py`
- ✅ Triggers: **ALL** CI pipelines (all services depend on shared/)
- ✅ Triggers: **ALL** Docker pipelines (on main/develop)

**Example 3**: Change `video-service/app/processor.py`
- ✅ Triggers: `video-ci.yml`, `video-docker.yml` (on main/develop)
- ❌ Skips: auth-ci, notification-ci

### Branch Strategy

- **`main`** branch:
  - Runs CI for changed services
  - Builds & pushes Docker images tagged `latest` and `main-<sha>`
  - Production-ready code

- **`develop`** branch:
  - Runs CI for changed services
  - Builds & pushes Docker images tagged `develop` and `develop-<sha>`
  - Development code

- **Feature branches**:
  - Runs CI for changed services only
  - No Docker builds (saves CI minutes)

### Using Pre-Built Images

Pull and run images from ghcr.io:

```bash
# Pull latest images
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull

# Start services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

**Note**: Update `YOUR_GITHUB_USERNAME` in `docker/docker-compose.prod.yml`

### Image Cleanup Policy

**Daily Cleanup** (runs at 2 AM UTC):
- Deletes untagged images older than 30 days
- Keeps last 10 tagged versions per service
- Can be manually triggered from Actions tab

### Local Development

Test changes before pushing:

```bash
# Auth service
flake8 auth-service/ shared/
pytest tests/test_auth.py -v

# Video service
flake8 video-service/ shared/
pytest tests/test_videos.py -v

# Notification service
flake8 notification-service/ shared/
```

### CI/CD Best Practices

1. **Small commits**: Easier to debug CI failures
2. **Test locally first**: Run lint and tests before pushing
3. **Check CI status**: Wait for green checkmarks before merging
4. **Monitor shared/**: Changes trigger all pipelines
5. **Use feature branches**: Test CI on your branch before merging

### Troubleshooting

**Pipeline not triggered:**
- Check if your changes match path filters
- Verify workflow file syntax (YAML indentation)
- Check GitHub Actions tab for errors

**Docker build fails:**
- Verify Dockerfile paths are correct
- Check `.dockerignore` isn't excluding required files
- Test build locally: `docker build -f auth-service/Dockerfile .`

**Tests fail in CI but pass locally:**
- Check environment variables in workflow
- Verify service containers (postgres, redis, rabbitmq) are healthy
- Check Python version matches (3.11)

**Image not found on ghcr.io:**
- Ensure workflow ran successfully
- Check package permissions (must be public)
- Visit: `https://github.com/YOUR_USERNAME?tab=packages`

## Future Enhancements

- **API Gateway**: Add Kong/Nginx for unified entry point and rate limiting
- **Service Discovery**: Implement Consul or Kubernetes service mesh
- **Logging**: Centralize logs with ELK stack
- **Kubernetes**: Deploy to K8s for production scalability
- **Database Isolation**: Separate databases per service (event sourcing)
- **Distributed Tracing**: Jaeger for service-to-service tracing

## Monitoring - Prometheus + Grafana

This project includes comprehensive monitoring with **Prometheus** for metrics collection and **Grafana** for visualization. Email alerting is configured via **Alertmanager** for critical incidents.

### Quick Start

**Environment Setup:**

Create a `.env` file or export environment variables for email notifications:

```bash
# SMTP Configuration (Gmail example)
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your-email@gmail.com
export SMTP_PASSWORD=your-app-password  # Use Gmail App Password, not main password
export SMTP_FROM=alerts@video-converter.local
export ALERT_EMAIL_TO=your-email@gmail.com,team@example.com

# Grafana Dashboard Credentials (optional)
export GRAFANA_USER=admin
export GRAFANA_PASSWORD=your-secure-password

# Start services with monitoring stack
docker-compose -f docker/docker-compose.yml up -d
```

**Access the Monitoring Stack:**

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9090 | (no auth) |
| **Alertmanager** | http://localhost:9093 | (no auth) |
| **Auth Service Metrics** | http://localhost:8001/metrics | (no auth) |
| **Video Service Metrics** | http://localhost:8002/metrics | (no auth) |
| **RabbitMQ Exporter** | http://localhost:9419 | (no auth) |
| **Redis Exporter** | http://localhost:9121 | (no auth) |
| **PostgreSQL Exporter** | http://localhost:9187 | (no auth) |

### Dashboards

Five pre-configured dashboards are automatically loaded in Grafana:

#### 1. **Executive Overview** - High-Level System Health
**Best for:** Stakeholders, managers, incident commanders

Displays:
- Overall system health status
- Current error rate (5m average)
- Active worker count
- SLO compliance status (95% of videos processed within 5 minutes)
- Error rate trend over 24 hours
- Video queue depth
- Video processing p95 latency vs SLO threshold
- Database connection pool usage
- Redis memory consumption

#### 2. **API Services** - Detailed Request Metrics
**Best for:** Backend engineers, API developers

Displays:
- Individual service health (Auth, Video, Notification)
- Overall error rate across all APIs
- p50/p95/p99 latency percentiles by service
- Request rate by service (requests/sec)
- Error rate breakdown by HTTP status code
- Response size distribution
- 24-hour error trend

#### 3. **Video Processing SLO** - SLO Compliance & Queue Management
**Best for:** Video processing team, DevOps engineers, SREs

Displays:
- **SLO Status Badge** ✓ Compliant / ✗ Violated (95% of videos < 5 minutes)
- Current p95 processing time (with threshold highlighting)
- Average processing time vs SLO
- Queue depth (pending task count)
- Task completion rate (success/failure ratio)
- Queue backlog trend (growth detection)
- Cumulative videos processed (24h total)
- Processing time distribution (p25/p50/p75/p95/p99 percentiles)

#### 4. **Celery Workers** - Worker Availability & Task Metrics
**Best for:** DevOps engineers, system administrators

Displays:
- Number of active workers
- Worker heartbeat status (health check >10 min timeout)
- Task success rate (5m average)
- Task failure rate (5m average)
- Worker heartbeat timeline (last heartbeat timestamp per worker)
- Time since last heartbeat (timeout detection)
- Task throughput by status (success/failed rate)
- Processing time distribution (p50/p95/p99)
- Cumulative task counts by status (24h)
- Worker availability timeline

#### 5. **Database & Infrastructure** - PostgreSQL, Redis, RabbitMQ Health
**Best for:** Database administrators, infrastructure engineers

Displays:
- Service health status (PostgreSQL, Redis, RabbitMQ)
- PostgreSQL connection pool usage % (with thresholds)
- Active database connections vs max allowed
- Query latency (sequential & index scans)
- Redis memory usage in GB
- Redis connected clients
- Redis operations/sec
- RabbitMQ message queue depth
- RabbitMQ message rate (published/delivered/acknowledged)
- PostgreSQL transaction rates (seq/index scans)
- PostgreSQL cache hit ratio

### Alert Rules

**13 Alert Rules** are configured in [docker/alerts.yml](docker/alerts.yml). Each alert can trigger email notifications via Alertmanager.

#### Critical Alerts 🔴 (Immediate notification)

| Alert | Condition | Duration | Action |
|-------|-----------|----------|--------|
| **HighErrorRate** | Error rate > 1% | 5 minutes | Email immediately |
| **VideoProcessingSLOViolation** | p95 processing time > 5 min | 5 minutes | Email immediately |
| **NoActiveWorkers** | Zero Celery workers alive | 2 minutes | Email immediately |
| **WorkerHeartbeatTimeout** | No heartbeat for > 10 minutes | 1 minute | Email immediately |
| **DatabaseConnectionErrors** | Cannot connect to PostgreSQL | 2 minutes | Email immediately |
| **RabbitMQConnectionError** | Cannot connect to RabbitMQ | 2 minutes | Email immediately |
| **RedisConnectionError** | Cannot connect to Redis | 2 minutes | Email immediately |

#### Warning Alerts ⚠️ (Batched hourly)

| Alert | Condition | Duration | Action |
|-------|-----------|----------|--------|
| **HighLatencyP95** | API p95 latency > 500ms | 5 minutes | Email (batched every 6h) |
| **DatabaseConnectionPoolSaturation** | DB pool usage > 80% | 5 minutes | Email (batched every 6h) |
| **VideoQueueBacklogGrowing** | Failure rate > success rate | 15 minutes | Email (batched every 6h) |
| **HighTaskFailureRate** | Task failure rate > 5% | 5 minutes | Email (batched every 6h) |
| **VideoProcessingAverageExceedsSLO** | Average processing > 5 min | 10 minutes | Email (batched every 6h) |

#### Alert Routing

**Alertmanager Configuration** ([docker/alertmanager.yml](docker/alertmanager.yml)):

- **Critical alerts**: Grouped by alertname, wait 10 seconds before sending, repeat every hour
- **Warning alerts**: Grouped by alertname, wait 5 minutes before batching, repeat every 6 hours
- **Email destination**: `${ALERT_EMAIL_TO}` (configured via environment variables)
- **SMTP**: Configurable via `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`

**Alert Suppression Rules (Inhibit Rules):**

- Don't alert on high error rate if database is down (prevents alert fatigue)
- Don't alert on queue backlog if no workers are available (prevents cascading alerts)

### Service Level Objectives (SLOs)

#### Video Processing SLO ✨
- **Objective**: 95% of videos processed within 5 minutes (p95 < 300 seconds)
- **Metric**: `histogram_quantile(0.95, celery_task_duration_seconds)`
- **Compliance Dashboard**: "Video Processing SLO" dashboard
- **Alert**: Triggers if p95 > 5 min for 5+ minutes consecutively

**Example SLO Calculation:**
```
Of 100 videos processed in a time window:
- 95 videos must complete within 5 minutes ✅
- Up to 5 videos (5%) can exceed the 5-minute threshold ✅
```

**Current Tracking:**
- Real-time p95 latency visible on "Video Processing SLO" dashboard
- Historical compliance over 24 hours via Grafana time-range selector
- Alert `VideoProcessingSLOViolation` fires when SLO is breached

#### API Error Rate SLO 🎯
- **Objective**: Error rate < 1% over any 5-minute window
- **Metric**: `rate(http_requests_total{status=~"5.."}[5m])`
- **Alert**: `HighErrorRate` fires if threshold exceeded for 5+ minutes

#### Worker Availability SLO ⚙️
- **Objective**: At least 1 Celery worker active at all times
- **Heartbeat Timeout**: 10 minutes (no heartbeat triggers alert)
- **Metric**: `celery_worker_alive`, `celery_worker_heartbeat_timestamp`
- **Alert**: `NoActiveWorkers` or `WorkerHeartbeatTimeout` fires immediately

#### Database Health SLO 🗄️
- **Objective**: Connection pool usage < 80%, zero connection errors
- **Metric**: `pg_stat_activity_count / pg_settings_max_connections`
- **Alert**: `DatabaseConnectionPoolSaturation` or `DatabaseConnectionErrors` fires if breached

### Metrics Collection

**Retention Policy:** 15 days (configured via Prometheus storage settings)

**Scrape Interval:** 15 seconds (all targets)

**Metrics by Service:**

| Service | Metrics | Endpoint |
|---------|---------|----------|
| **Auth Service** | Request count, latency, status codes, response size | GET :8001/metrics |
| **Video Service** | Request count, latency, status codes, response size | GET :8002/metrics |
| **Notification Service** | Request count, latency, status codes | GET :8001/metrics |
| **Celery Workers** | Task duration, success/failure count, worker alive status, heartbeat | Signals-based collection |
| **PostgreSQL** | Connection count, query latency, transaction rate, cache hits | Port 9187 |
| **Redis** | Memory usage, connected clients, operations/sec, hit ratio | Port 9121 |
| **RabbitMQ** | Queue depth, message rate, consumer count | Port 9419 |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                          │
├──────────────────────────────────────────────────────────────┤
│
│  ┌─────────────┐    ┌──────────────┐    ┌──────────┐
│  │ Prometheus  │───→│  Alertmanager│───→│  Email   │
│  │ (9090)      │    │  (9093)      │    │  SMTP    │
│  └──────┬──────┘    └──────────────┘    └──────────┘
│         │                      ↑
│         │                      │
│         └──────────────────────┘
│              (scrape metrics)
│
│  ┌─────────────────────────────────────────────────────┐
│  │ Grafana Dashboards (port 3000)                      │
│  │ - Executive Overview                                │
│  │ - API Services                                      │
│  │ - Video Processing SLO                              │
│  │ - Celery Workers                                    │
│  │ - Database & Infrastructure                         │
│  └─────────────────────────────────────────────────────┘
│         ↑
│         │ (queries metrics)
│         │
│  ┌──────┴────┬────────────┬──────────┬──────────┬──────────┐
│  │Prometheus │ PostgreSQL │  Redis   │RabbitMQ  │FastAPI   │
│  │:9090      │:9187       │ :9121    │ :9419    │:8001/2   │
│  │           │ exporter   │exporter  │exporter  │/metrics  │
│  └───────────┴────────────┴──────────┴──────────┴──────────┘
│
└──────────────────────────────────────────────────────────────┘
```

### Troubleshooting

**Prometheus is not scraping metrics:**
1. Check Prometheus status: http://localhost:9090/targets
2. Verify services are running: `docker-compose ps`
3. Check docker network: `docker network inspect microservices`
4. Review Prometheus logs: `docker-compose logs prometheus`

**Alerts not sending emails:**
1. Verify SMTP credentials in docker-compose environment variables
2. Check Alertmanager status: http://localhost:9093
3. Review Alertmanager logs: `docker-compose logs alertmanager`
4. Test SMTP connection:
   ```bash
   docker exec alertmanager swaks --to $ALERT_EMAIL_TO --from $SMTP_FROM \
     --server $SMTP_HOST:$SMTP_PORT --auth-user $SMTP_USER \
     --auth-password $SMTP_PASSWORD --tls
   ```

**Grafana dashboards not loading:**
1. Verify Prometheus data source: http://localhost:3000/datasources
2. Check data source connection: Click "Test" on Prometheus datasource
3. Import dashboards manually if auto-provisioning fails:
   - Settings → Dashboards → Import → Upload JSON from `docker/grafana/provisioning/dashboards/`

**Missing Celery metrics:**
1. Restart video-worker: `docker-compose restart video-worker`
2. Check worker logs: `docker-compose logs video-worker`
3. Verify celery-prometheus-exporter installed: `docker-compose exec video-worker pip list | grep prometheus`

### Extending Monitoring

**Add Custom Metrics:**

In any FastAPI service main.py:
```python
from prometheus_client import Counter, Histogram

# Define custom metrics
custom_counter = Counter('my_metric_total', 'Custom metric count')
custom_histogram = Histogram('my_request_duration_seconds', 'Custom request duration')

# Use in route handler
@app.get("/custom-endpoint")
def custom_endpoint():
    custom_counter.inc()
    custom_histogram.observe(0.5)
    return {"status": "ok"}
```

**Add Custom Alert Rule:**

Edit [docker/alerts.yml](docker/alerts.yml) and add to the `rules` section:
```yaml
- alert: MyCustomAlert
  expr: custom_counter > 1000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Custom alert triggered"
    description: "Custom counter value is {{ $value }}"
```

**Reload Prometheus rules:**
```bash
curl -X POST http://localhost:9090/-/reload
```

## License

MIT


A Python FastAPI-based video converter for uploading, processing, and downloading videos in ZIP format. Modular design for easy transition to microservices.

## Features
- User authentication (JWT)
- Asynchronous video processing (multiple videos)
- Status tracking per user
- Webhook notifications (event-driven)
- PostgreSQL + Redis for data/cache

## Setup
1. Clone the repo.
2. Copy `.env.example` to `.env` and fill in values.
3. Run with Docker Compose: `docker-compose -f docker/docker-compose.yml up --build`
4. Or locally: `pip install -r requirements.txt`, then `uvicorn app.main:app --reload`

## API Endpoints
- POST /auth/signup
- POST /auth/login
- POST /videos/upload (requires auth)
- GET /videos/status (requires auth)
- GET /videos/download/{video_id} (requires auth)

## Testing
Run `pytest` in the root directory.

## MVP vs Production Project

### This is an MVP (Minimum Viable Product)
An MVP is a lightweight version to validate the core concept quickly. It includes:
- ✅ Core features (upload, process, download videos)
- ✅ Basic authentication (JWT)
- ✅ Simple tests (5 test cases)
- ✅ Minimal infrastructure (PostgreSQL, Redis, FastAPI)

### A Production Project would add:

**1. Comprehensive tests**
- *MVP*: 5 basic tests (happy path)
- *Production*: 50+ tests including error cases, security, edge cases
  - Example: `test_upload_without_auth()`, `test_invalid_file_type()`, `test_sql_injection_prevention()`

**2. Advanced monitoring**
- *MVP*: None
- *Production*: Logs, metrics, alerts
  - Example: Prometheus metrics for failed uploads, ELK stack for centralized logs, Grafana dashboards

**3. Security hardening**
- *MVP*: Just JWT
- *Production*: Rate limiting, CORS, input sanitization, encryption
  - Example: Limit 10 uploads/hour per user, validate file types, encrypt videos at rest

**4. Performance optimization**
- *MVP*: Synchronous processing, no caching
- *Production*: Async workers, database indexing, caching
  - Example: Celery workers for video processing, Redis caching for status queries, indexed user IDs

**5. Scalability**
- *MVP*: Single server
- *Production*: Load balancing, horizontal scaling, CDN
  - Example: Nginx load balancer, multiple app servers, CloudFront for video delivery

**6. Deployment**
- *MVP*: Run locally or basic Docker
- *Production*: CI/CD, blue-green deployments, rollback strategies
  - Example: GitHub Actions auto-tests, Kubernetes deployments, automated rollbacks on failure

**7. Documentation**
- *MVP*: README only
- *Production*: API docs, architecture diagrams, runbooks
  - Example: Swagger/OpenAPI, deployment guide, troubleshooting guide

**8. Data backup & recovery**
- *MVP*: None
- *Production*: Database backups, disaster recovery plans
  - Example: Daily backups to S3, RTO/RPO targets defined, tested recovery procedures

**9. User management**
- *MVP*: Just signup/login
- *Production*: Admin panel, roles, permissions, audit logs
  - Example: Admin can view all uploads, users can only see their own, activity logs for compliance

**10. Compliance**
- *MVP*: None
- *Production*: GDPR compliance, encryption, audit trails
  - Example: Delete user data on request, encrypt sensitive fields, log all access

**Summary**: This MVP proves the concept works. Production readiness requires scalability, reliability, security, and operational excellence.

## Future: Microservices
Refactor each module (auth, videos, notifications) into separate FastAPI apps, deploy with Kubernetes, add messaging (RabbitMQ) for inter-service comms.