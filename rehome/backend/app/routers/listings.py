"""Marketplace listings. Contract: docs/04-api-contract.md"""
from typing import Literal
from fastapi import APIRouter
from app.agents import orchestrator

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("")
async def list_listings(status: Literal["active", "expired"] | None = None):
    return {"listings": orchestrator.listings(status)}
