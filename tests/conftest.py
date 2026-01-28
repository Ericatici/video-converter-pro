"""
Pytest configuration for integration tests
Sets up test fixtures and shared test utilities
"""
import pytest
import os
import sys
from pathlib import Path
import tempfile

# Create a temporary database file for tests
test_db = tempfile.mktemp(suffix=".db")

# CRITICAL: Set environment variables BEFORE any imports
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"
os.environ["TESTING"] = "true"

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "auth-service"))
sys.path.insert(0, str(project_root / "video-service"))
sys.path.insert(0, str(project_root / "notification-service"))


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create database tables for testing"""
    # Import after environment is set
    from shared.database import Base, engine
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except:
            pass
