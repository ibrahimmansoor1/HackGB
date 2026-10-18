"""Activity feed. Frontend polls GET /api/events?after=<last id>.
`run_id` narrows it to one agent run (every step of one concierge run)."""
from fastapi import APIRouter
from app.agents import orchestrator

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(after: int = 0, run_id: str | None = None):
    return {"events": orchestrator.events(after, run_id)}
