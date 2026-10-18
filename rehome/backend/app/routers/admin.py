"""Demo helpers. Seed runs without the model (items are pre-parsed in app/seed_data.py)."""
from fastapi import APIRouter
from app.agents import orchestrator
from app.schemas import ExpiryOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/seed")
async def seed():
    """Load the demo inventory (docs/04). Safe to call twice: no duplicates."""
    return {"seeded": await orchestrator.seed_demo()}


@router.post("/simulate-expiry", response_model=ExpiryOut)
async def simulate_expiry():
    """Fast-forward 30 days: unsold listings go back to the donation pool."""
    return await orchestrator.expire_listings()
