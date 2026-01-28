"""
Simple webhook test server to receive video processing notifications.

Run this locally on port 3001 to receive webhook events from the notification service.

Usage:
    python webhook_test_server.py
"""

from fastapi import FastAPI, Request
from datetime import datetime
import uvicorn

app = FastAPI(title="Webhook Test Server")

@app.get("/webhook")
async def get_webhook(request: Request):
    """Handle GET requests to webhook endpoint (for testing in browser)"""
    print("\n" + "="*60)
    print(f"🔍 GET REQUEST at {datetime.now().isoformat()}")
    print("="*60)
    print("Method: GET")
    print(f"URL: {request.url}")
    print(f"Client: {request.client.host}:{request.client.port}")
    print("="*60 + "\n")
    
    return {
        "status": "ok",
        "message": "Webhook endpoint is active",
        "methods": {
            "GET": "For testing/browser access (this endpoint)",
            "POST": "For receiving webhook notifications"
        },
        "example_payload": {
            "event": "video.completed",
            "timestamp": "2026-01-27T12:00:00",
            "data": {
                "video_id": 1,
                "username": "user",
                "status": "completed"
            }
        }
    }

@app.post("/webhook")
async def receive_webhook(request: Request):
    """Receive webhook notifications from video processing service"""
    try:
        body = await request.body()
        if not body:
            print("⚠️  Empty request body received (test request)")
            return {"status": "ok", "message": "Webhook endpoint is working. Send JSON payload for processing."}
        
        payload = await request.json()
    except Exception as e:
        print(f"⚠️  Invalid JSON payload: {e}")
        return {"status": "error", "message": f"Invalid JSON payload: {str(e)}"}
    
    event_type = payload.get("event", "unknown")
    timestamp = payload.get("timestamp", "N/A")
    data = payload.get("data", payload)
    
    print("\n" + "="*60)
    print(f"📥 POST WEBHOOK at {datetime.now().isoformat()}")
    print("="*60)
    print(f"Event Type: {event_type}")
    print(f"Timestamp: {timestamp}")
    print(f"Full Payload: {payload}")
    print("="*60 + "\n")
    
    return {"status": "received", "event": event_type}

@app.get("/health")
def health():
    return {"status": "ok", "service": "webhook-test-server"}

if __name__ == "__main__":
    print("🚀 Starting Webhook Test Server on http://localhost:3001")
    print("📨 Listening for video processing events...")
    uvicorn.run(app, host="0.0.0.0", port=3001)
