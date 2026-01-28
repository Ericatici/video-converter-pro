# Webhook Integration Guide

This document explains how to integrate with the video processing webhook notifications.

## Overview

The notification service sends HTTP POST requests to your configured webhook URL whenever video processing events occur.

## Webhook Configuration

Set your webhook URL in the `.env` file:

```env
WEBHOOK_URL=http://your-domain.com/webhook
```

For local development:
```env
WEBHOOK_URL=http://localhost:3000/webhook
```

For Docker (accessing host machine from container):
```env
WEBHOOK_URL=http://host.docker.internal:3000/webhook
```

## Event Types

### 1. Video Completed (`video.completed`)

Triggered when a video is successfully processed.

**Payload Example:**
```json
{
  "event": "video.completed",
  "timestamp": "2026-01-16T10:30:00",
  "data": {
    "user_id": 123,
    "username": "testuser",
    "video_id": 456,
    "video_filename": "myvideo.mp4",
    "status": "completed",
    "download_url": "/videos/download/456"
  }
}
```

### 2. Video Error (`video.error`)

Triggered when video processing fails.

**Payload Example:**
```json
{
  "event": "video.error",
  "timestamp": "2026-01-16T10:30:00",
  "data": {
    "user_id": 123,
    "username": "testuser",
    "video_id": 456,
    "video_filename": "myvideo.mp4",
    "error": "FFmpeg conversion failed: Invalid codec",
    "status": "error"
  }
}
```

## Webhook Endpoint Requirements

Your webhook endpoint should:

1. **Accept POST requests** with JSON payload
2. **Respond quickly** (< 5 seconds recommended)
3. **Return HTTP 2xx** status code to acknowledge receipt
4. **Handle retries** gracefully (same event may be sent multiple times)

## Example Implementations

### Python (FastAPI)

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.json()
    
    event_type = payload["event"]
    data = payload["data"]
    
    if event_type == "video.completed":
        # Send email, SMS, push notification, etc.
        send_notification(
            user_id=data["user_id"],
            message=f"Your video {data['video_filename']} is ready!"
        )
    
    elif event_type == "video.error":
        # Alert user about error
        send_error_alert(
            user_id=data["user_id"],
            error=data["error"]
        )
    
    return {"status": "received"}
```

### Node.js (Express)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/webhook', (req, res) => {
  const { event, data } = req.body;
  
  if (event === 'video.completed') {
    // Handle completion
    console.log(`Video ${data.video_id} completed for user ${data.username}`);
    sendNotification(data.user_id, `Your video is ready!`);
  }
  
  if (event === 'video.error') {
    // Handle error
    console.log(`Video ${data.video_id} failed: ${data.error}`);
    sendErrorAlert(data.user_id, data.error);
  }
  
  res.json({ status: 'received' });
});

app.listen(3000);
```

### PHP

```php
<?php
// webhook.php

$payload = json_decode(file_get_contents('php://input'), true);

$event = $payload['event'];
$data = $payload['data'];

if ($event === 'video.completed') {
    // Send email or notification
    sendEmail(
        $data['username'],
        "Video Ready",
        "Your video {$data['video_filename']} is ready to download!"
    );
}

if ($event === 'video.error') {
    // Alert about error
    sendErrorEmail(
        $data['username'],
        "Video Processing Error",
        $data['error']
    );
}

header('Content-Type: application/json');
echo json_encode(['status' => 'received']);
```

## Testing Your Webhook

### 1. Start the Test Server

Use the provided test server:

```bash
python webhook_test_server.py
```

This will listen on `http://localhost:3000/webhook` and log all incoming events.

### 2. Test with curl

```bash
curl -X POST http://localhost:3000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": "video.completed",
    "timestamp": "2026-01-16T10:30:00",
    "data": {
      "user_id": 1,
      "username": "test",
      "video_id": 1,
      "video_filename": "test.mp4",
      "status": "completed",
      "download_url": "/videos/download/1"
    }
  }'
```

### 3. Test with Real Video Processing

1. Start your webhook server
2. Start the microservices: `docker-compose up -d`
3. Upload a video through the API
4. Watch your webhook server receive the completion event

## Security Considerations

### 1. Webhook Signature Verification

Add HMAC signature verification to ensure webhooks are from your service:

```python
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 2. HTTPS Only

In production, always use HTTPS for webhook URLs:

```env
WEBHOOK_URL=https://your-domain.com/webhook
```

### 3. IP Whitelisting

Restrict webhook endpoint to only accept requests from your service IPs.

### 4. Rate Limiting

Implement rate limiting on your webhook endpoint to prevent abuse.

## Webhook Delivery Guarantees

- **At-least-once delivery**: Events may be delivered multiple times
- **No guaranteed order**: Events may arrive out of order
- **Best-effort**: Failed deliveries are logged but not automatically retried (you can add retry logic)

## Troubleshooting

### Webhook not receiving events

1. **Check webhook URL** in docker-compose.yml:
   ```yaml
   WEBHOOK_URL=http://host.docker.internal:3000/webhook
   ```

2. **Check notification service logs**:
   ```bash
   docker logs notification-service
   ```

3. **Verify webhook server is running**:
   ```bash
   curl http://localhost:3000/health
   ```

4. **Check firewall rules** allow incoming connections on port 3000

### Events arriving out of order

Use the `timestamp` field to order events client-side.

### Duplicate events

Implement idempotency using the `video_id` as a unique identifier.

## Integration Examples

### Send Email via SendGrid

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.json()
    
    if payload["event"] == "video.completed":
        message = Mail(
            from_email='noreply@example.com',
            to_emails=f"{payload['data']['username']}@example.com",
            subject='Your video is ready!',
            html_content=f"<p>Video {payload['data']['video_filename']} is ready to download!</p>"
        )
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        sg.send(message)
    
    return {"status": "received"}
```

### Update External Database

```python
import asyncpg

@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.json()
    
    conn = await asyncpg.connect('postgresql://...')
    
    await conn.execute('''
        INSERT INTO video_events (event_type, user_id, video_id, timestamp)
        VALUES ($1, $2, $3, $4)
    ''', payload["event"], payload["data"]["user_id"], 
         payload["data"]["video_id"], payload["timestamp"])
    
    await conn.close()
    return {"status": "received"}
```

### Trigger Slack Notification

```python
import httpx

@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.json()
    
    if payload["event"] == "video.error":
        slack_webhook = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
        message = {
            "text": f"⚠️ Video processing failed for user {payload['data']['username']}: {payload['data']['error']}"
        }
        async with httpx.AsyncClient() as client:
            await client.post(slack_webhook, json=message)
    
    return {"status": "received"}
```

## Next Steps

1. Implement your custom webhook handler
2. Add security measures (HTTPS, signature verification)
3. Set up monitoring and alerting
4. Configure production webhook URL
5. Test thoroughly before deployment

For questions, refer to the main README.md or check the `webhook_test_server.py` example.
