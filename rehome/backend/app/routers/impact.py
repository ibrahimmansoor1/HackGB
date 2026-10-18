"""Impact dashboard stats (continuous aggregate). Contract: docs/04-api-contract.md"""
from fastapi import APIRouter
from app.agents import orchestrator
from app.schemas import ImpactOut

router = APIRouter(prefix="/api/impact", tags=["impact"])


@router.get("", response_model=ImpactOut)
async def impact():
    return orchestrator.impact()
