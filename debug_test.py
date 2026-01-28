import os
import tempfile

test_db = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"

import sys
from pathlib import Path

sys.path.insert(0, str(Path('.') / "auth-service"))

from shared.database import Base, engine
Base.metadata.create_all(bind=engine)

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print("Routes available:")
for route in app.routes:
    methods = getattr(route, 'methods', ['*'])
    print(f"  {list(methods)}: {route.path}")

print("\nTesting signup...")
resp = client.post("/auth/signup", json={"username": "test", "password": "pass"})
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")

print("\nTesting login...")
resp2 = client.post("/auth/login", json={"username": "test", "password": "pass"})
print(f"Status: {resp2.status_code}")
print(f"Response: {resp2.json()}")
