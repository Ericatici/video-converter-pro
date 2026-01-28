import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path('.') / "tests"))

# Run conftest setup
from conftest import *

# Import auth app
sys.path.insert(0, str(Path('.') / "auth-service"))
from app.main import app as auth_app
from fastapi.testclient import TestClient

print("\n=== Auth App Routes ===")
for route in auth_app.routes:
    methods = getattr(route, 'methods', ['*'])
    print(f"  {list(methods)}: {route.path}")

print("\n=== Testing Auth Client ===")
auth_client = TestClient(auth_app)
resp = auth_client.post("/auth/signup", json={"username": "test123", "password": "pass"})
print(f"Signup status: {resp.status_code}")
print(f"Signup response: {resp.json() if resp.status_code == 200 else resp.text}")

resp2 = auth_client.post("/auth/login", json={"username": "test123", "password": "pass"})
print(f"Login status: {resp2.status_code}")
print(f"Login response: {resp2.json() if resp2.status_code == 200 else resp2.text}")
