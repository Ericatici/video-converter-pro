"""
Integration tests for Video Service (microservice)
Tests the video-service endpoints using FastAPI TestClient
"""
import pytest
from fastapi.testclient import TestClient
import zipfile
import io
import uuid

# Direct imports will work after conftest.py sets up paths
from app.main import app as auth_app  # From auth-service
import sys
from pathlib import Path

# Import video service app
video_service_path = Path(__file__).parent.parent / "video-service"
sys.path.insert(0, str(video_service_path))
from app.main import app as video_app  # From video-service


@pytest.fixture(scope="function")
def auth_client():
    """Create test client for auth service"""
    with TestClient(auth_app) as client:
        yield client


@pytest.fixture(scope="function")
def video_client():
    """Create test client for video service"""
    with TestClient(video_app) as client:
        yield client


@pytest.fixture
def auth_token(auth_client):
    """Create a test user and return auth token"""
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    
    # Signup
    signup_resp = auth_client.post(
        "/auth/signup",
        json={"username": username, "password": "pass123"}
    )
    assert signup_resp.status_code in [200, 400], f"Signup failed: {signup_resp.text}"
    
    # Login to get token
    login_resp = auth_client.post(
        "/auth/login",
        json={"username": username, "password": "pass123"}
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    
    data = login_resp.json()
    assert "access_token" in data, f"No access_token in response: {data}"
    return data["access_token"]


class TestVideoService:
    """Video Service Integration Tests"""
    
    def test_health_check(self, video_client):
        """Test health endpoint"""
        response = video_client.get("/health")
        assert response.status_code == 200
    
    def test_upload_video_success(self, video_client, auth_token):
        """Test successful video upload"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create a fake video file
        video_content = b"fake mp4 video content here"
        files = {"file": ("test.mp4", video_content, "video/mp4")}
        
        response = video_client.post(
            "/videos/upload",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "video_id" in data
        assert data["status"] == "queued"
    
    def test_upload_without_auth(self, video_client):
        """Test upload without authentication token"""
        video_content = b"fake mp4 video content"
        files = {"file": ("test.mp4", video_content, "video/mp4")}
        
        response = video_client.post(
            "/videos/upload",
            files=files
        )
        
        assert response.status_code == 403
    
    def test_upload_unsupported_format(self, video_client, auth_token):
        """Test upload with unsupported file format"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Unsupported format: .txt
        files = {"file": ("test.txt", b"not a video", "text/plain")}
        
        response = video_client.post(
            "/videos/upload",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Unsupported" in response.json().get("detail", "")
    
    def test_get_status_empty(self, video_client, auth_client):
        """Test getting status with no videos"""
        # Create a unique user
        username = uuid.uuid4().hex[:12]
        auth_client.post(
            "/auth/signup",
            json={"username": username, "password": "pass123"}
        )
        login_response = auth_client.post(
            "/auth/login",
            json={"username": username, "password": "pass123"}
        )
        token = login_response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        response = video_client.get(
            "/videos/status",
            headers=headers
        )
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_status_after_upload(self, video_client, auth_token):
        """Test getting status after upload"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Upload video
        video_content = b"fake mp4 video content"
        files = {"file": ("test.mp4", video_content, "video/mp4")}
        
        upload_response = video_client.post(
            "/videos/upload",
            files=files,
            headers=headers
        )
        
        video_id = upload_response.json()["video_id"]
        
        # Get status
        status_response = video_client.get(
            "/videos/status",
            headers=headers
        )
        
        assert status_response.status_code == 200
        videos = status_response.json()
        assert len(videos) >= 1
        assert any(v["id"] == video_id for v in videos)
    
    def test_get_status_without_auth(self, video_client):
        """Test get status without authentication"""
        response = video_client.get("/videos/status")
        assert response.status_code == 403
    
    def test_download_nonexistent_video(self, video_client, auth_token):
        """Test downloading a video that doesn't exist"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = video_client.get(
            "/videos/download/99999",
            headers=headers
        )
        
        assert response.status_code == 404
    
    def test_upload_zip_with_video(self, video_client, auth_token):
        """Test uploading a ZIP file containing a video"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create a ZIP with a fake video
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("video.mp4", b"fake mp4 content")
        
        zip_buffer.seek(0)
        files = {"file": ("video.zip", zip_buffer.read(), "application/zip")}
        
        response = video_client.post(
            "/videos/upload",
            files={"file": files["file"]},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "video_id" in data
    
    def test_upload_zip_without_video(self, video_client, auth_token):
        """Test uploading a ZIP without video file"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create a ZIP without video
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("text.txt", b"just text")
        
        zip_buffer.seek(0)
        files = {"file": ("no_video.zip", zip_buffer.read(), "application/zip")}
        
        response = video_client.post(
            "/videos/upload",
            files={"file": files["file"]},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "video file" in response.json().get("detail", "").lower()
    
    def test_cache_consistency(self, video_client, auth_token):
        """Test that Redis cache returns consistent data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # First call - should hit database
        response1 = video_client.get(
            "/videos/status",
            headers=headers
        )
        data1 = response1.json()
        
        # Second call - should hit cache
        response2 = video_client.get(
            "/videos/status",
            headers=headers
        )
        data2 = response2.json()
        
        # Both should return same data
        assert data1 == data2
        assert response1.status_code == 200
        assert response2.status_code == 200