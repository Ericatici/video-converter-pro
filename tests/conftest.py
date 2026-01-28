"""
Pytest configuration for integration tests
Sets up test fixtures and shared test utilities
"""
import pytest
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "auth-service"))
sys.path.insert(0, str(project_root / "video-service"))
sys.path.insert(0, str(project_root / "notification-service"))


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables"""
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    yield
