"""Activity feed. Frontend polls GET /api/events?after=<last id>."""
from fastapi import APIRouter
from app.core import db

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(after: int = 0):
    return {"events": db.list_events(after)}
