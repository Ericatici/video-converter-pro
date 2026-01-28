"""
Integration tests for Auth Service (microservice)
Tests the auth-service endpoints via HTTP calls
Requires auth-service running on http://localhost:8001
"""
import pytest
import httpx
import uuid

AUTH_SERVICE_URL = "http://localhost:8001"


def unique_username():
    """Generate a unique username for test isolation"""
    return f"user_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def client():
    """Create HTTP client for auth service"""
    return httpx.Client(base_url=AUTH_SERVICE_URL, timeout=10.0)


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
