"""
Integration tests for Video Service (microservice)
Tests the video-service endpoints using FastAPI TestClient
"""
import pytest
from fastapi.testclient import TestClient
import zipfile
import io
import uuid
import sys
import os
from pathlib import Path

# Set up test environment BEFORE importing apps
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_video.db"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["SECRET_KEY"] = "test-secret-key"

# Cache for auth modules to restore after loading video app
_auth_modules_cache = {}


@pytest.fixture(scope="module")
def auth_app():
    """Get auth service app - loaded first"""
    global _auth_modules_cache
    
    auth_path = Path(__file__).parent.parent / "auth-service"
    sys.path.insert(0, str(auth_path))
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # Import auth app
    from app import main as auth_main
    auth_application = auth_main.app
    
    # Cache auth modules for later restoration
    _auth_modules_cache = {
        'app': sys.modules.get('app'),
        'app.main': sys.modules.get('app.main'),
        'app.routes': sys.modules.get('app.routes'),
    }
    
    return auth_application


@pytest.fixture(scope="module") 
def video_app(auth_app):
    """Get video service app - loaded after auth with proper isolation"""
    global _auth_modules_cache
    
    # Remove auth-service app modules to load video-service
    for key in list(sys.modules.keys()):
        if key.startswith('app.') or key == 'app':
            del sys.modules[key]
    
    # Add video-service to path
    video_path = Path(__file__).parent.parent / "video-service"  
    sys.path.insert(0, str(video_path))
    
    # Import video app
    from app import main as video_main
    video_application = video_main.app
    
    # Store video modules
    video_modules = {
        'app': sys.modules.get('app'),
        'app.main': sys.modules.get('app.main'),
    }
    
    # Restore auth modules so auth_client fixture works
    for key, module in _auth_modules_cache.items():
        if module is not None:
            sys.modules[key] = module
    
    return video_application


@pytest.fixture
def auth_client(auth_app):
    """Create test client for auth service"""
    return TestClient(auth_app)


@pytest.fixture
def video_client(video_app):
    """Create test client for video service"""
    return TestClient(video_app)


@pytest.fixture
def auth_token(auth_client):
    """Create a test user and return auth token"""
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    
    # Signup
    signup_resp = auth_client.post(
        "/auth/signup",
        json={"username": username, "password": "pass123"}
    )
    if signup_resp.status_code not in [200, 400]:
        raise AssertionError(f"Signup failed with {signup_resp.status_code}: {signup_resp.text}")
    
    # Login to get token
    login_resp = auth_client.post(
        "/auth/login",
        json={"username": username, "password": "pass123"}
    )
    if login_resp.status_code != 200:
        raise AssertionError(f"Login failed with {login_resp.status_code}: {login_resp.text}")
    
    data = login_resp.json()
    if "access_token" not in data:
        raise AssertionError(f"No access_token in response: {data}")
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
        files = [("files", ("test.mp4", video_content, "video/mp4"))]
        
        response = video_client.post(
            "/videos/upload",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] == 1
        assert len(data["videos"]) == 1
        assert "video_id" in data["videos"][0]
        assert data["videos"][0]["status"] == "queued"
    
    def test_upload_without_auth(self, video_client):
        """Test upload without authentication token"""
        video_content = b"fake mp4 video content"
        files = [("files", ("test.mp4", video_content, "video/mp4"))]
        
        response = video_client.post(
            "/videos/upload",
            files=files
        )
        
        assert response.status_code == 403
    
    def test_upload_unsupported_format(self, video_client, auth_token):
        """Test upload with unsupported file format"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Unsupported format: .txt
        files = [("files", ("test.txt", b"not a video", "text/plain"))]
        
        response = video_client.post(
            "/videos/upload",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 400
        assert "No valid video files" in response.json().get("detail", "")
    
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
        files = [("files", ("test.mp4", video_content, "video/mp4"))]
        
        upload_response = video_client.post(
            "/videos/upload",
            files=files,
            headers=headers
        )
        
        video_id = upload_response.json()["videos"][0]["video_id"]
        
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
        files = [("files", ("video.zip", zip_buffer.read(), "application/zip"))]
        
        response = video_client.post(
            "/videos/upload",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] == 1
        assert len(data["videos"]) == 1
        assert "video_id" in data["videos"][0]
    
    def test_upload_zip_without_video(self, video_client, auth_token):
        """Test uploading a ZIP without video file"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create a ZIP without video
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("text.txt", b"just text")
        
        zip_buffer.seek(0)
        files = [("files", ("no_video.zip", zip_buffer.read(), "application/zip"))]
        
        response = video_client.post(
            "/videos/upload",
            files=files,
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