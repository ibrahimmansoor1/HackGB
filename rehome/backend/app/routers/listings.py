"""Marketplace listings. Contract: docs/04-api-contract.md"""
from fastapi import APIRouter
from app.agents import orchestrator

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("")
async def list_listings(status: str | None = None):
    return {"listings": orchestrator.listings(status)}
