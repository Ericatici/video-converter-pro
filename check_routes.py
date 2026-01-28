import sys
from pathlib import Path

sys.path.insert(0, str(Path('.') / 'auth-service'))

from app.main import app

print("Auth Service Routes:")
for route in app.routes:
    methods = getattr(route, 'methods', ['*'])
    print(f"  {methods}: {route.path}")
