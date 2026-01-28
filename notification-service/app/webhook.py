import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx
import json
from shared.config import settings
from shared.database import SessionLocal
from shared.models import User, Video

def send_error_notification(user_id: int, video_id: int, error: str):
    """Send error notification via webhook"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        video = db.query(Video).filter(Video.id == video_id).first()
        
        if not user:
            print(f"User {user_id} not found")
            return
        
        payload = {
            "event": "video.error",
            "timestamp": video.created_at.isoformat() if video else None,
            "data": {
                "user_id": user_id,
                "username": user.username,
                "video_id": video_id,
                "video_filename": video.filename if video else "unknown",
                "error": error,
                "status": "error"
            }
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                settings.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        
        print(f"Error notification webhook sent for user {user.username}")
    except Exception as e:
        print(f"Error sending webhook notification: {e}")
    finally:
        db.close()

def send_completion_notification(user_id: int, video_id: int):
    """Send completion notification via webhook"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        video = db.query(Video).filter(Video.id == video_id).first()
        
        if not user:
            print(f"User {user_id} not found")
            return
        
        if not video:
            print(f"Video {video_id} not found")
            return
        
        payload = {
            "event": "video.completed",
            "timestamp": video.created_at.isoformat(),
            "data": {
                "user_id": user_id,
                "username": user.username,
                "video_id": video_id,
                "video_filename": video.filename,
                "status": "completed",
                "download_url": f"/videos/download/{video_id}"
            }
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                settings.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        
        print(f"Completion notification webhook sent for user {user.username}")
    except Exception as e:
        print(f"Error sending webhook notification: {e}")
    finally:
        db.close()
