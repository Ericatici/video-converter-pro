import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from .routes import router

app = FastAPI(title="Notification Service - Video Converter")

# Add Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(router, prefix="/health", tags=["health"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service"}
