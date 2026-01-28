"""
Integration tests for Auth Service (microservice)
Tests the auth-service endpoints using FastAPI TestClient
"""
import pytest
import uuid
import sys
import os
from pathlib import Path
from fastapi.testclient import TestClient

# Set up test environment BEFORE importing app
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///test_auth.db"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["SECRET_KEY"] = "test-secret-key"

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def unique_username():
    """Generate a unique username for test isolation"""
    return f"user_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def auth_app():
    """Load the auth-service app"""
    # Change to auth-service directory
    auth_service_dir = Path(__file__).parent.parent / "auth-service"
    sys.path.insert(0, str(auth_service_dir))
    
    from app.main import app
    return app


@pytest.fixture
def client(auth_app):
    """
    TestClient fixture for in-memory testing.
    No need to run auth-service separately.
    """
    return TestClient(auth_app)


class TestAuthService:
    """Auth Service Integration Tests"""
    
    def test_health_check(self, client):
        """Test health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_signup_success(self, client):
        """Test successful user signup"""
        username = unique_username()
        response = client.post(
            "/auth/signup",
            json={"username": username, "password": "testpass123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_signup_duplicate_user(self, client):
        """Test signup with duplicate username"""
        username = unique_username()
        # First signup
        client.post(
            "/auth/signup",
            json={"username": username, "password": "pass123"}
        )
        
        # Duplicate signup
        response = client.post(
            "/auth/signup",
            json={"username": username, "password": "pass456"}
        )
        assert response.status_code == 400
    
    def test_login_success(self, client):
        """Test successful login"""
        username = unique_username()
        # Signup first
        client.post(
            "/auth/signup",
            json={"username": username, "password": "pass123"}
        )
        
        # Login
        response = client.post(
            "/auth/login",
            json={"username": username, "password": "pass123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
    
    def test_login_invalid_credentials(self, client):
        """Test login with wrong password"""
        username = unique_username()
        # Signup
        client.post(
            "/auth/signup",
            json={"username": username, "password": "correct"}
        )
        
        # Wrong password
        response = client.post(
            "/auth/login",
            json={"username": username, "password": "wrong"}
        )
        assert response.status_code == 400
    
    def test_verify_token_valid(self, client):
        """Test token verification"""
        username = unique_username()
        # Signup first
        client.post(
            "/auth/signup",
            json={"username": username, "password": "pass"}
        )
        
        # Login to get token
        login_response = client.post(
            "/auth/login",
            json={"username": username, "password": "pass"}
        )
        token = login_response.json()["access_token"]
        
        # Verify token
        response = client.post(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["username"] == username
    
    def test_verify_token_invalid(self, client):
        """Test token verification with invalid token"""
        response = client.post(
            "/auth/verify",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401
