# Webhook Migration Summary

## Changes Made

Successfully migrated notification system from **Email (SMTP)** to **Webhooks (HTTP POST)**.

---

## Files Modified

### 1. **Configuration** (`shared/config.py`)
- ✅ Removed: `smtp_server`, `smtp_port`, `smtp_user`, `smtp_pass`
- ✅ Added: `webhook_url` with default value

### 2. **Notification Service**
- ✅ Renamed: `email.py` → `webhook.py`
- ✅ Replaced SMTP logic with HTTP POST requests using `httpx`
- ✅ Updated payload structure with rich event data
- ✅ Added timeout handling (10 seconds)

### 3. **Event Listeners** (`notification-service/app/listeners.py`)
- ✅ Updated import: `from .webhook import ...`
- ✅ Modified event handlers to pass `video_id` parameter

### 4. **Dependencies** (`notification-service/requirements.txt`)
- ✅ Added: `httpx==0.25.1` for HTTP requests
- ✅ No longer needed: SMTP libraries (Python stdlib)

### 5. **Docker Compose** (`docker/docker-compose.yml`)
- ✅ Removed SMTP environment variables from all services
- ✅ Added `WEBHOOK_URL` to all services
- ✅ Set default: `http://host.docker.internal:3000/webhook`

### 6. **Documentation**
- ✅ Updated: `README.md` - webhook references
- ✅ Updated: `QUICKSTART.md` - webhook setup
- ✅ Created: `WEBHOOK_GUIDE.md` - complete integration guide
- ✅ Created: `webhook_test_server.py` - testing utility

---

## New Webhook Payload Format

### Video Completed Event
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

### Video Error Event
```json
{
  "event": "video.error",
  "timestamp": "2026-01-16T10:30:00",
  "data": {
    "user_id": 123,
    "username": "testuser",
    "video_id": 456,
    "video_filename": "myvideo.mp4",
    "error": "FFmpeg conversion failed",
    "status": "error"
  }
}
```

---

## How to Use

### 1. Start the Test Webhook Server (Locally)

```bash
python webhook_test_server.py
```

This starts a server on `http://localhost:3000/webhook` that logs all incoming events.

### 2. Update Environment Variables

In your `.env` file:

```env
# Remove old SMTP config (no longer needed)
# SMTP_SERVER=...
# SMTP_PORT=...
# SMTP_USER=...
# SMTP_PASS=...

# Add webhook URL
WEBHOOK_URL=http://localhost:3000/webhook
```

For production, point to your actual webhook endpoint:
```env
WEBHOOK_URL=https://your-api.com/webhook
```

### 3. Start Microservices

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 4. Test End-to-End

1. Upload a video through the API
2. Watch the webhook test server receive the `video.completed` event
3. Implement your custom webhook handler based on the guide

---

## Benefits of Webhooks vs Email

| Feature | Email (SMTP) | Webhooks (HTTP) |
|---------|-------------|-----------------|
| **Speed** | Slower (SMTP handshake) | Fast (HTTP POST) |
| **Reliability** | Depends on email delivery | Direct HTTP response |
| **Integration** | Limited (email only) | Any system (DB, SMS, Slack, etc.) |
| **Customization** | Email templates | Full control over logic |
| **Testing** | Need email server | Simple HTTP endpoint |
| **Monitoring** | Hard to track delivery | Easy logging & retries |
| **Credentials** | SMTP user/pass needed | No credentials needed |
| **Flexibility** | Text/HTML only | JSON, custom formats |

---

## Integration Examples

### Send Email via SendGrid
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event"] == "video.completed":
        sg = SendGridAPIClient(SENDGRID_KEY)
        mail = Mail(
            from_email='noreply@example.com',
            to_emails=f"{payload['data']['username']}@example.com",
            subject='Video Ready',
            html_content='<p>Your video is ready!</p>'
        )
        sg.send(mail)
    return {"status": "ok"}
```

### Send SMS via Twilio
```python
from twilio.rest import Client

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    if payload["event"] == "video.completed":
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        client.messages.create(
            body=f"Video {payload['data']['video_filename']} is ready!",
            from_='+1234567890',
            to='+0987654321'
        )
    return {"status": "ok"}
```

### Post to Slack
```python
import httpx

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient() as client:
        await client.post(
            SLACK_WEBHOOK_URL,
            json={"text": f"✅ Video {payload['data']['video_id']} completed!"}
        )
    return {"status": "ok"}
```

### Update Database
```python
@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    async with database.transaction():
        await database.execute(
            "UPDATE videos SET status = :status WHERE id = :id",
            {"status": payload["data"]["status"], "id": payload["data"]["video_id"]}
        )
    return {"status": "ok"}
```

---

## Testing

### Test with curl
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
      "status": "completed"
    }
  }'
```

### Test with the provided server
```bash
# Terminal 1: Start webhook server
python webhook_test_server.py

# Terminal 2: Send test request (above curl command)
```

---

## Security Best Practices

1. **Use HTTPS in production**: `WEBHOOK_URL=https://...`
2. **Implement signature verification** (see WEBHOOK_GUIDE.md)
3. **Add rate limiting** to prevent abuse
4. **Validate payload structure** before processing
5. **Use IP whitelisting** if possible

---

## Troubleshooting

### Webhooks not being received

1. **Check webhook URL configuration**:
   ```bash
   docker exec auth-service env | grep WEBHOOK_URL
   ```

2. **Verify webhook server is running**:
   ```bash
   curl http://localhost:3000/health
   ```

3. **Check notification service logs**:
   ```bash
   docker logs notification-service
   ```

4. **Test webhook connectivity from container**:
   ```bash
   docker exec notification-service curl http://host.docker.internal:3000/health
   ```

### Webhook timeout errors

- Ensure your webhook endpoint responds within 10 seconds
- Move heavy processing to background tasks
- Return HTTP 200 immediately, process async

---

## Next Steps

1. ✅ Read `WEBHOOK_GUIDE.md` for detailed integration examples
2. ✅ Implement your custom webhook handler
3. ✅ Add authentication/signature verification
4. ✅ Deploy webhook endpoint to production
5. ✅ Update `WEBHOOK_URL` in production environment
6. ✅ Monitor webhook delivery success rates

---

## Files to Review

- **WEBHOOK_GUIDE.md** - Complete integration guide
- **webhook_test_server.py** - Example webhook server
- **README.md** - Updated with webhook information
- **QUICKSTART.md** - Quick reference with webhook setup

---

**Migration Complete!** 🎉

Your notification system now uses modern webhooks instead of email, providing:
- ⚡ Faster delivery
- 🔧 More flexibility
- 🔍 Better monitoring
- 🚀 Easier integration with any system
