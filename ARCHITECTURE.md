# Microservices Architecture - Complete Design

Production-ready microservices platform with async processing, event-driven notifications, and comprehensive monitoring.

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATION                                   │
│                    (Web Browser / Mobile / Desktop)                           │
└──────────┬──────────────────────┬──────────────────────┬──────────────────────┘
           │                      │                      │
           │ POST /auth/*         │ POST /videos/upload  │ GET /videos/status
           │                      │                      │
           ▼                      ▼                      ▼
      ┌─────────────┐         ┌──────────────┐     ┌──────────────┐
      │Auth Service │         │Video Service │     │Video Service │
      │(Port 8001)  │         │(Port 8002)   │     │(Port 8002)   │
      │             │         │              │     │(Cache layer) │
      │- signup     │         │- upload      │     │              │
      │- login      │         │- process     │     │- status      │
      │- verify     │         │- queue       │     │(Redis 120s)  │
      └──────┬──────┘         └────────┬─────┘     └────────┬──────┘
             │                        │                    │
             │                        │ Invalidate cache   │
             └────────────┬───────────┴────────────────────┘
                          │
                          ▼
             ┌──────────────────────┐
             │   PostgreSQL 15      │
             │  (Shared Database)   │
             │                      │
             │  Tables:             │
             │  - users (indexed)   │
             │  - videos (indexed)  │
             └──────────────────────┘
```

## Service Architecture

### 1. Auth Service (Port 8001)
**Synchronous authentication & authorization**

```
POST /auth/signup { username, password }
  ├─ Validate input (length, format, XSS prevention)
  ├─ Hash password: bcrypt(password, cost=12) [~100ms]
  ├─ Store in DB: INSERT users
  └─ Response: {user_id, username}

POST /auth/login { username, password }
  ├─ Fetch user: SELECT * FROM users WHERE username=?
  ├─ Verify hash: bcrypt.verify(password, stored_hash) [~100ms]
  ├─ Generate JWT: jwt.encode({user_id, username, exp: now+24h})
  └─ Response: {access_token, expires_in: 86400}

POST /auth/verify { token } [Used by other services]
  ├─ Verify signature: jwt.decode(token, SECRET)
  ├─ Check expiration: exp > now
  ├─ Extract payload: {user_id, username}
  └─ Response: {user_id, username} or 401 Unauthorized

Technologies:
├─ FastAPI 0.104.1
├─ PyJWT (python-jose)
├─ bcrypt
├─ SQLAlchemy ORM
├─ Prometheus metrics (/metrics endpoint)
└─ PostgreSQL (shared)
```

### 2. Video Service (Port 8002)
**Synchronous API with async background processing**

```
POST /videos/upload
  ├─ Verify JWT token locally (no external call)
  ├─ Save file to /uploads/
  ├─ Create DB record: INSERT videos (status='uploaded')
  ├─ Queue Celery task: apply_async(process_video, args=(video_id,))
  ├─ Invalidate Redis cache: DEL video_status:{username}
  ├─ Response: {video_id, status: 'queued'} [IMMEDIATE - <100ms]
  └─ Note: Upload ZIP files supported (.mp4, .mov, .mkv, .avi, .webm)

GET /videos/status
  ├─ Extract user_id from JWT token
  ├─ Check Redis: GET video_status:{username}
  │  ├─ HIT: Return cached result [<5ms]
  │  └─ MISS: Query DB [~50ms]
  ├─ Query DB: SELECT * FROM videos WHERE user_id=?
  ├─ Store in Redis: SET video_status:{username} <data> EX 120
  ├─ Response: [{video_id, status, filename, created_at, ...}]
  └─ Cache TTL: 120 seconds

GET /videos/download/{video_id}
  ├─ Verify JWT token
  ├─ Check DB: SELECT * FROM videos WHERE id=? AND user_id=?
  ├─ Verify status='completed'
  ├─ Create ZIP: {video_id_converted.mp4}
  ├─ Stream file: /processed/video_id_converted.mp4
  └─ Response: Binary ZIP file

Technologies:
├─ FastAPI 0.104.1
├─ Celery 5.3.4 (task queuing)
├─ RabbitMQ client (event publishing)
├─ Redis (caching with 120s TTL)
├─ SQLAlchemy ORM
├─ Prometheus metrics
├─ PostgreSQL (shared)
└─ JWT verification (same keys as Auth Service)

Cache Invalidation:
├─ POST /videos/upload → DEL video_status:{username}
├─ Video processing complete → DEL video_status:{username}
└─ Video processing error → DEL video_status:{username}
```

### 3. Video Worker (Celery Task Queue)
**Asynchronous background video processing**

```
Celery Worker
├─ Connect to RabbitMQ broker (amqp://guest:guest@rabbitmq:5672/)
├─ Consume tasks from queue: celery
├─ Process video (blocking task):
│  │
│  ├─ 1. Dequeue task: {video_id: 123}
│  │
│  ├─ 2. Read video file
│  │    ├─ File path: /uploads/123_original.mp4
│  │    └─ Validate: Check format, file size, duration
│  │
│  ├─ 3. FFmpeg conversion
│  │    ├─ Command: ffmpeg -i input.mp4 -c:v libx264 -crf 23 output.mp4
│  │    ├─ Timeout: 30 minutes (configurable)
│  │    └─ Handle errors: Invalid codec, disk full, timeout
│  │
│  ├─ 4. Save processed video
│  │    ├─ File path: /processed/123_converted.mp4
│  │    ├─ Verify checksum
│  │    └─ Delete original file (optional)
│  │
│  ├─ 5. Update database
│  │    ├─ UPDATE videos SET status='completed', completed_at=NOW()
│  │    ├─ Or on error: status='error', error_message='...'
│  │    └─ DB commit (durable)
│  │
│  ├─ 6. Invalidate cache
│  │    └─ DEL video_status:{username}
│  │
│  └─ 7. Publish event to RabbitMQ
│     ├─ Topic: video_events
│     ├─ Routing key: video.completed or video.error
│     ├─ Payload:
│     │  {
│     │    "video_id": 123,
│     │    "user_id": 456,
│     │    "username": "john_doe",
│     │    "status": "completed" | "error",
│     │    "error_message": "optional",
│     │    "timestamp": "2026-01-16T10:30:00Z"
│     │  }
│     └─ Persistent message (survives broker restart)
│
├─ Scalability:
│  ├─ Run multiple workers: docker-compose up --scale video-worker=5
│  ├─ Each worker processes one video at a time (sequential)
│  ├─ Celery distributes tasks round-robin
│  └─ Performance: 1 worker = 1 video/min, 5 workers = 5 videos/min

Technologies:
├─ Celery 5.3.4
├─ RabbitMQ client
├─ FFmpeg 4.x (system command)
├─ SQLAlchemy ORM (DB update)
├─ Redis client (cache invalidation)
└─ PostgreSQL (shared)

Error Handling:
├─ Task failure → Publish video.error event
├─ FFmpeg error → Capture stderr, save to DB
├─ DB error → Retry with exponential backoff
├─ Network error → Celery auto-retry (3 times default)
└─ Timeout → Task revoked after 30 minutes
```

### 4. Notification Service (Event Consumer)
**Asynchronous event-driven notifications**

```
Notification Service (Listener Process)
├─ Connect to RabbitMQ
├─ Create queue: notification_queue (persistent, durable)
├─ Bind to topic: video_events with pattern: video.*
├─ Start listener loop:
│  │
│  ├─ Receive message from queue
│  ├─ Parse JSON: {video_id, user_id, status, ...}
│  │
│  ├─ If status='completed':
│  │  ├─ Query DB: SELECT * FROM users WHERE id=?
│  │  ├─ Build webhook payload:
│  │  │  {
│  │  │    "event": "video.completed",
│  │  │    "timestamp": "2026-01-16T10:30:00Z",
│  │  │    "data": {
│  │  │      "user_id": 123,
│  │  │      "username": "john",
│  │  │      "video_id": 456,
│  │  │      "video_filename": "myvideo.mp4",
│  │  │      "status": "completed",
│  │  │      "download_url": "http://localhost:8002/videos/download/456"
│  │  │    }
│  │  │  }
│  │  ├─ HTTP POST to WEBHOOK_URL (configured in env)
│  │  ├─ Timeout: 30 seconds
│  │  ├─ Retry logic: 3 attempts with exponential backoff
│  │  └─ Log result (success/failure)
│  │
│  ├─ Else if status='error':
│  │  ├─ Build error webhook
│  │  ├─ Include error_message in payload
│  │  └─ HTTP POST to webhook
│  │
│  └─ Acknowledge message (only after processing)
│     └─ RabbitMQ removes from queue
│
├─ Delivery Guarantees:
│  ├─ At-least-once (may send duplicates)
│  ├─ Persistent queue (survives restart)
│  ├─ Ack-based consumption
│  └─ Dead-letter queue for permanent failures

Technologies:
├─ FastAPI 0.104.1 (health check endpoint)
├─ pika (RabbitMQ client library)
├─ httpx (async HTTP client for webhooks)
├─ SQLAlchemy ORM (user lookup)
└─ PostgreSQL (shared)

Configuration:
├─ WEBHOOK_URL: http://your-webhook-receiver.com/webhook
├─ RabbitMQ URL: amqp://guest:guest@rabbitmq:5672/
├─ Topic: video_events
├─ Queue: notification_queue
└─ Routing pattern: video.*
```

## Infrastructure Services

### PostgreSQL (Shared Database)
```
Connection: postgresql://user:password@db:5432/videoconverter
Port: 5432

Tables:
├─ users
│  ├─ id: BIGSERIAL PRIMARY KEY
│  ├─ username: VARCHAR(255) UNIQUE NOT NULL
│  ├─ email: VARCHAR(255)
│  ├─ password_hash: VARCHAR(255) NOT NULL
│  ├─ created_at: TIMESTAMP DEFAULT NOW()
│  ├─ updated_at: TIMESTAMP DEFAULT NOW()
│  └─ INDEX(username) ← Fast auth lookups
│
└─ videos
   ├─ id: BIGSERIAL PRIMARY KEY
   ├─ user_id: BIGINT NOT NULL REFERENCES users(id)
   ├─ filename: VARCHAR(500) NOT NULL
   ├─ original_path: VARCHAR(1000)
   ├─ processed_path: VARCHAR(1000)
   ├─ status: VARCHAR(50) NOT NULL ('uploaded', 'processing', 'completed', 'error')
   ├─ error_message: TEXT
   ├─ created_at: TIMESTAMP DEFAULT NOW()
   ├─ completed_at: TIMESTAMP
   ├─ INDEX(user_id) ← Fast user lookup
   ├─ INDEX(status) ← For queue queries
   └─ INDEX(created_at) ← For sorting

Access:
├─ Auth Service: Read/Write (users)
├─ Video Service: Read/Write (videos)
├─ Notification Service: Read (users, videos)
└─ Video Worker: Read/Write (videos)
```

### RabbitMQ (Message Broker)
```
URL: amqp://guest:guest@rabbitmq:5672/
Management UI: http://localhost:15672 (guest/guest)
Port: 5672

Topic Exchange: video_events
├─ Type: Topic (pattern-based routing)
├─ Durable: true (survives broker restart)
├─ Auto-delete: false
├─ Arguments: None

Queues:
├─ notification_queue
│  ├─ Durable: true
│  ├─ Auto-delete: false
│  ├─ Exclusive: false (can have multiple consumers)
│  ├─ Binding: video_events with routing pattern: video.*
│  ├─ Dead Letter Exchange: None (can add for failures)
│  └─ Message TTL: None (infinite)

Routing Keys:
├─ video.completed: Video processing succeeded
└─ video.error: Video processing failed

Message Flow:
├─ Video Worker: Publish to topic with routing key
├─ Topic Exchange: Route to all matching queues
├─ Notification Queue: Persistent storage
└─ Notification Service: Consume and process

Message Format (JSON):
{
  "video_id": 123,
  "user_id": 456,
  "username": "john_doe",
  "status": "completed" | "error",
  "error_message": "optional",
  "timestamp": "2026-01-16T10:30:00Z"
}

Durability:
├─ Queue is persistent
├─ Messages are persistent (delivery_mode=2)
├─ Survives broker restart
└─ Ack-based consumption (manual ack after processing)
```

### Redis (Cache Layer)
```
URL: redis://redis:6379
Port: 6379

Cache Strategy:
├─ Cache Key: video_status:{username}
├─ TTL: 120 seconds
├─ Data: [{video_id, status, filename, created_at, ...}]
└─ Eviction: LRU (Least Recently Used)

Operations:
├─ GET video_status:{username} → Cached result [<5ms]
├─ SET video_status:{username} <data> EX 120 → Store
├─ DEL video_status:{username} → Invalidate
└─ FLUSHDB → Clear all cache (rare)

Hit Rate:
├─ First request: Cache miss (DB query ~50ms)
├─ Subsequent requests (within 120s): Cache hit (<5ms)
├─ After 120s: Cache miss (DB query again)

Invalidation:
├─ POST /videos/upload → Delete cache immediately
├─ Video processing complete → Delete cache immediately
└─ Video processing error → Delete cache immediately

Memory Usage:
├─ Typical: <100MB (cached for 120s)
├─ Peak: <500MB (with multiple users)
└─ No persistence (data can be regenerated from DB)
```

### Prometheus & Grafana (Monitoring)
```
Prometheus (9090):
├─ Scrapes metrics every 15 seconds
├─ Stores 15-day retention
├─ Targets:
│  ├─ Auth Service (:8001/metrics)
│  ├─ Video Service (:8002/metrics)
│  ├─ Celery Workers (custom exporter)
│  ├─ PostgreSQL Exporter (:9187)
│  ├─ Redis Exporter (:9121)
│  └─ RabbitMQ Exporter (:9419)
└─ Queries time-series data

Grafana (3000):
├─ Dashboards:
│  ├─ Executive Overview (system health)
│  ├─ API Services (request metrics)
│  ├─ Video Processing SLO (95% within 5 min)
│  ├─ Celery Workers (task metrics)
│  └─ Database & Infrastructure (resource usage)
├─ Alerts (Alertmanager):
│  ├─ Critical: Immediate email
│  ├─ Warning: Batched 6-hourly
│  └─ Info: Dashboard only
└─ Default login: admin/admin

Key Metrics:
├─ API requests/sec
├─ Latency percentiles (p50, p95, p99)
├─ Error rate (5xx responses)
├─ Video processing time
├─ Worker availability
├─ DB connection pool usage
└─ Cache hit ratio
```

## Data Flow Diagrams

### Synchronous Request Flow (Auth)
```
Client
  │
  ├─ POST /auth/signup { username: "john", password: "pass123" }
  │
  ▼
Auth Service (8001)
  │
  ├─ Validate input
  ├─ Hash password: bcrypt(pass123, cost=12) [~100ms]
  ├─ INSERT users: INSERT INTO users (username, password_hash) VALUES (?, ?)
  │
  ▼
PostgreSQL
  │
  ├─ Execute INSERT
  ├─ Return: user_id = 1
  │
  ▼
Auth Service (8001)
  │
  ├─ Build response: {user_id: 1, username: "john"}
  │
  ▼
Client receives: {user_id: 1, username: "john"}
Total time: ~150ms
```

### Asynchronous Processing Flow
```
Step 1: Upload (Synchronous, <100ms)
─────────────────────────────────────
Client
  │ POST /videos/upload with JWT
  ▼
Video Service (8002)
  │ 1. Verify JWT token
  │ 2. Save file: /uploads/123_original.mp4
  │ 3. INSERT videos (status='uploaded')
  │ 4. Queue Celery task: apply_async()
  │ 5. DELETE video_status:{username} (cache)
  │ 6. Return {video_id: 123, status: 'queued'}
  │
  ▼
Client receives: {video_id: 123, status: 'queued'}
Response time: <100ms

Step 2: Processing (Asynchronous, 30 seconds - 30 minutes)
──────────────────────────────────────────────────────────
Celery Queue (RabbitMQ)
  │
  ▼
Video Worker (picks up task)
  │
  ├─ Dequeue: {video_id: 123}
  ├─ Read: /uploads/123_original.mp4
  ├─ Process: ffmpeg -i input.mp4 -c:v libx264 output.mp4
  ├─ Save: /processed/123_converted.mp4
  ├─ UPDATE videos SET status='completed'
  ├─ DELETE video_status:{username} (cache)
  ├─ Publish to RabbitMQ: {video_id: 123, status: 'completed'}
  │
  ▼
RabbitMQ Topic Exchange (video_events)
  │
  ▼
Notification Service (listening)
  │
  ├─ Receive event
  ├─ Query DB: SELECT * FROM users WHERE id=?
  ├─ Build webhook: {event: "video.completed", ...}
  ├─ HTTP POST to webhook URL
  ├─ Acknowledge message
  │
  ▼
User's Webhook Endpoint receives: {event: "video.completed", ...}

Step 3: Download (Synchronous, <200ms)
───────────────────────────────────────
Client
  │ GET /videos/download/123 with JWT
  ▼
Video Service (8002)
  │
  ├─ Verify JWT token
  ├─ SELECT * FROM videos WHERE id=123
  ├─ Verify status='completed'
  ├─ Create ZIP: /processed/123_converted.mp4
  ├─ Stream file
  │
  ▼
Client receives: ZIP file
Response time: <200ms
```

### Caching Flow
```
Request 1 (Cache cold):
───────────────────────
Client: GET /videos/status
  │
  ▼
Video Service (8002)
  │
  ├─ Get user_id from JWT
  ├─ Check Redis: GET video_status:john
  │  └─ Not found (cache miss)
  ├─ Query DB: SELECT * FROM videos WHERE user_id=?
  │  └─ DB returns: [{video_id: 1, status: "completed", ...}]
  ├─ Store in Redis: SET video_status:john [...] EX 120
  ├─ Return to client
  │
  ▼
Client receives: [{video_id: 1, status: "completed", ...}]
Latency: ~100ms (includes DB query)


Request 2 (Cache warm, within 120 seconds):
─────────────────────────────────────────────
Client: GET /videos/status
  │
  ▼
Video Service (8002)
  │
  ├─ Get user_id from JWT
  ├─ Check Redis: GET video_status:john
  │  └─ Found! (cache hit)
  ├─ Return cached result immediately
  │
  ▼
Client receives: [{video_id: 1, status: "completed", ...}]
Latency: <5ms (pure cache hit)


Cache Invalidation:
───────────────────
Event: User uploads video
  │
  ▼
Video Service
  │
  ├─ DELETE video_status:{username}
  │
  ▼
Next GET /videos/status will miss cache and query DB again
```

## Service Dependencies

```
PostgreSQL (Core)
    ├─→ Auth Service (required for startup)
    ├─→ Video Service (required for startup)
    ├─→ Notification Service (required for startup)
    └─→ Video Worker (required for startup)

RabbitMQ (Message Broker)
    ├─→ Video Service (required for startup)
    ├─→ Video Worker (required for startup)
    └─→ Notification Service (required for startup)

Redis (Cache - Optional)
    └─→ Video Service (degrades gracefully if missing)

Auth Service
    └─→ Video Service (token verification)
        └─ Uses /auth/verify endpoint
        └─ Synchronous HTTP call
        └─ JWT signature validation

Video Service
    └─→ Video Worker (task queue)
        └─ Via RabbitMQ
        └─ Asynchronous

Video Worker
    └─→ Notification Service (event publishing)
        └─ Via RabbitMQ
        └─ Asynchronous
```

## Scaling Strategy

### Horizontal Scaling
```
Scale Video Workers:
├─ Command: docker-compose up --scale video-worker=10
├─ Creates 10 parallel workers
├─ Each processes one video at a time
├─ Celery distributes tasks round-robin
├─ Performance: 10x throughput (10 videos/min)
└─ Bottleneck: FFmpeg CPU usage per worker

Scale API Services:
├─ Deploy multiple Video Service instances
├─ Use load balancer (Nginx, HAProxy, Traefik)
├─ Session-less (JWT-based, no session affinity needed)
├─ DB connection pooling (max 20 connections/instance)
└─ Performance: Linear with instance count

Scale Database:
├─ PostgreSQL read replicas for SELECT queries
├─ Notification Service can use replica
├─ Video Service and Worker use primary (master)
├─ Backup strategy: Daily snapshots
└─ RTO: 30 minutes, RPO: 1 day

Scale Cache:
├─ Redis clustering (not needed for typical usage)
├─ Replication for high availability
├─ Persistence: Optional (data regenerated from DB)
└─ Memory: Monitor and scale if needed
```

### Vertical Scaling
```
Increase CPU:
├─ More workers per instance
├─ Faster FFmpeg processing
├─ Parallel task execution
└─ Limits: GIL, single-threaded workers

Increase Memory:
├─ Cache more results in Redis
├─ Faster query execution (more indexes)
├─ Larger batch processing
└─ Limits: RAM available, diminishing returns

Increase Disk:
├─ Store more videos in /uploads and /processed
├─ Longer retention without cleanup
├─ Backup storage
└─ Limits: Storage capacity, cost
```

## Disaster Recovery

### Failure Scenarios
```
1. Video Worker crashes
   ├─ Task remains in RabbitMQ queue
   ├─ Another worker picks it up
   ├─ Auto-recovery via Docker (restart policy)
   └─ No data loss (queue is persistent)

2. PostgreSQL goes down
   ├─ All services fail (hard dependency)
   ├─ Restore from backup: ~30 minutes
   ├─ Restore data: ~1 hour
   └─ RTO: 1.5 hours, RPO: 1 day

3. RabbitMQ goes down
   ├─ Video Service can't queue tasks
   ├─ Notification Service can't consume events
   ├─ Queued tasks persist on restart
   ├─ Auto-recovery via Docker
   └─ No data loss (queue is persistent)

4. Redis goes down
   ├─ Cache unavailable (not critical)
   ├─ Video Service queries DB directly
   ├─ Performance degrades: ~100ms per request
   ├─ Auto-recovery via Docker
   └─ No data loss (regenerated from DB)

5. Video Service crashes
   ├─ Other instances continue (with load balancer)
   ├─ Failed requests fail gracefully
   ├─ Auto-recovery via Docker
   └─ No data loss (DB is durable)
```

### Backup Strategy
```
PostgreSQL:
├─ Daily full backup → S3
├─ Hourly incremental → NFS
├─ Retention: 30 days
├─ Test restore monthly
├─ Encryption: AES-256
└─ Versioning: 3 versions

Volumes (/uploads, /processed):
├─ Daily backup → S3
├─ Retention: 7 days
├─ Checksum verification
├─ Compression: gzip
└─ Encrypted transfer

Configuration:
├─ docker-compose.yml → Git (version controlled)
├─ prometheus.yml → Git
├─ alertmanager.yml → Git
├─ All secrets → AWS Secrets Manager
└─ Never store secrets in Git
```

## Security Architecture

### Authentication
```
JWT (JSON Web Token):
├─ Algorithm: HS256 (HMAC with SHA-256)
├─ Payload: {user_id, username, exp: now+24h}
├─ Signature: hmac_sha256(payload, SECRET)
├─ Expiration: 24 hours
└─ Stored: Authorization header (not cookies)

Password Hashing:
├─ Algorithm: bcrypt
├─ Cost factor: 12 (2^12 iterations)
├─ Time to hash: ~100ms
├─ Salt: Generated per password
└─ Never store plaintext passwords

Token Verification:
├─ Signature validation: jwt.decode(token, SECRET)
├─ Expiration check: exp > now
├─ Extract claims: {user_id, username}
├─ Database query (optional): Verify user still exists
└─ Return: Authorized or 401 Unauthorized
```

### Input Validation
```
Username:
├─ Length: 3-255 characters
├─ Pattern: [a-zA-Z0-9_.-] (alphanumeric, underscore, dot, dash)
├─ Unique: Check database before insert
└─ XSS prevention: No HTML/scripts allowed

Password:
├─ Minimum length: 8 characters
├─ Complexity: Optional (not enforced)
├─ Hashed before storage: bcrypt
└─ Never stored plaintext

Video Upload:
├─ File size: Max 5GB (configurable)
├─ Format: .mp4, .mov, .mkv, .avi, .webm only
├─ Validation: Magic bytes (file signature)
├─ Filename sanitization: Remove special characters
└─ Path traversal prevention: Use secure path joining

JSON Input:
├─ Validate all JSON payloads
├─ Schema validation: Pydantic models
├─ Type checking: Strict types
├─ SQL injection prevention: Parameterized queries
└─ XSS prevention: HTML escaping on output
```

### HTTPS & TLS
```
Production:
├─ Always use HTTPS (TLS 1.3)
├─ Valid certificate (not self-signed)
├─ HSTS header: Enforce HTTPS
├─ Cipher suites: Strong only (no RC4, DES, etc.)
└─ Certificate renewal: Automated (Let's Encrypt)

Development:
├─ HTTP allowed (no TLS)
├─ No real data (test data only)
├─ Self-signed certificates optional
└─ HTTPS not enforced
```

This architecture is **production-ready for immediate deployment** and **horizontally scalable for high traffic**!
