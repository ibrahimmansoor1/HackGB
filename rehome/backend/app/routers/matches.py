"""Claim a match (A1 -> A2). Contract: docs/04-api-contract.md"""
from fastapi import APIRouter, HTTPException
from app.agents import orchestrator
from app.schemas import AcceptIn, AcceptOut

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.post("/accept", response_model=AcceptOut)
async def accept(body: AcceptIn):
    try:
        return await orchestrator.accept_match(body.request_id, body.item_id)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)
