"""Demo helpers. Seed runs without the model (items are pre-parsed in app/seed_data.py)."""
from fastapi import APIRouter, HTTPException
from app.agents import orchestrator
from app.schemas import ExpiryOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/seed")
async def seed():
    """Load the demo inventory (docs/04). Safe to call twice: no duplicates."""
    return {"seeded": await orchestrator.seed_demo()}


@router.post("/reset")
async def reset():
    """Clear the demo inventory for another rehearsal (closes active listings first)."""
    try:
        return await orchestrator.reset_demo()
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)


@router.post("/simulate-expiry", response_model=ExpiryOut)
async def simulate_expiry():
    """Fast-forward 30 days: unsold listings go back to the donation pool."""
    return await orchestrator.expire_listings()
