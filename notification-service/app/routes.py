import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter

router = APIRouter()

@router.get("")
def health_check():
    return {"status": "ok"}
