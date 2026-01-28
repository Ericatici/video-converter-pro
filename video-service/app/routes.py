import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from shared.database import get_db
from shared.models import User, Video
from shared.auth_utils import verify_token
from .celery_app import process_video_task
import zipfile
import os
import httpx
import shutil
import json
from typing import List
from shared.redis_client import get_redis_client

UPLOAD_DIR = Path("uploads")
PROCESSED_DIR = Path("processed")
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
STATUS_CACHE_TTL_SECONDS = 120

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

redis_client = get_redis_client()


def _status_cache_key(username: str) -> str:
    return f"videos:status:{username}"


def _get_cached_status(username: str):
    try:
        cached = redis_client.get(_status_cache_key(username))
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"Cache read failed: {e}")
    return None


def _set_cached_status(username: str, data):
    try:
        redis_client.setex(_status_cache_key(username), STATUS_CACHE_TTL_SECONDS, json.dumps(data))
    except Exception as e:
        print(f"Cache write failed: {e}")


def _invalidate_status_cache(username: str):
    try:
        redis_client.delete(_status_cache_key(username))
    except Exception as e:
        print(f"Cache invalidate failed: {e}")

router = APIRouter()
security = HTTPBearer()

AUTH_SERVICE_URL = "http://auth-service:8001"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify token with auth service"""
    token = credentials.credentials
    username = verify_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return username

@router.post("/upload")
async def upload_video(files: List[UploadFile] = File(...), db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    print(f"Uploading {len(files)} video(s) for user {current_user}")
    user = db.query(User).filter(User.username == current_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    uploaded_videos = []
    
    for file in files:
        original_filename = file.filename
        tmp_path = UPLOAD_DIR / original_filename

        with open(tmp_path, "wb") as f:
            f.write(await file.read())

        final_filename = original_filename

        if tmp_path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(tmp_path, "r") as zip_ref:
                    members = [m for m in zip_ref.namelist() if Path(m).suffix.lower() in ALLOWED_VIDEO_EXTENSIONS]
                    if not members:
                        tmp_path.unlink()
                        continue  # Skip invalid zip files
                    member = members[0]
                    target_path = UPLOAD_DIR / Path(member).name
                    with zip_ref.open(member) as source, open(target_path, "wb") as dest:
                        shutil.copyfileobj(source, dest)
                    final_filename = target_path.name
            except zipfile.BadZipFile:
                tmp_path.unlink()
                continue  # Skip invalid zip files
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        else:
            if tmp_path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
                tmp_path.unlink()
                continue  # Skip unsupported formats

        video = Video(filename=final_filename, user_id=user.id)
        db.add(video)
        db.commit()
        db.refresh(video)
        print(f"Video saved with id {video.id}")

        # Queue async task instead of processing synchronously
        process_video_task.delay(video.id)
        
        uploaded_videos.append({"video_id": video.id, "filename": final_filename, "status": "queued"})
    
    _invalidate_status_cache(current_user)
    
    return {"uploaded": len(uploaded_videos), "videos": uploaded_videos}

@router.get("/status")
def get_status(db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    cached = _get_cached_status(current_user)
    if cached is not None:
        return cached

    user = db.query(User).filter(User.username == current_user).first()
    videos = db.query(Video).filter(Video.user_id == user.id).all()
    response = [{"id": v.id, "filename": v.filename, "status": v.status} for v in videos]

    _set_cached_status(current_user, response)
    return response

@router.get("/by-user/{username}")
def get_videos_by_user(username: str, db: Session = Depends(get_db)):
    """
    Get all videos for a specific user by username.
    
    Parameters:
    - username: The username to query videos for
    
    Returns:
    - List of videos with id, filename, and status
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    
    videos = db.query(Video).filter(Video.user_id == user.id).all()
    response = [{"id": v.id, "filename": v.filename, "status": v.status} for v in videos]
    
    return {
        "username": username,
        "total_videos": len(response),
        "videos": response
    }

@router.get("/download/{video_id}")
def download_video(video_id: int, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video or video.user.username != current_user or video.status != "completed":
        raise HTTPException(status_code=404, detail="Video not found or not ready")
    
    converted_path = PROCESSED_DIR / f"{video_id}_converted.mp4"
    if not converted_path.exists():
        raise HTTPException(status_code=404, detail="Converted file missing")

    base_name = Path(video.filename).stem
    zip_path = PROCESSED_DIR / f"{video_id}.zip"

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write(converted_path, f"{base_name}_converted.mp4")

    return FileResponse(str(zip_path), media_type='application/zip', filename=f"{base_name}_converted.zip")
