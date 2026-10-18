"""Requester endpoints. Contract: docs/04-api-contract.md"""
from fastapi import APIRouter
from app.agents import orchestrator
from app.schemas import RequestIn, RequestOut

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("", response_model=RequestOut, status_code=201)
async def create_request(body: RequestIn):
    return await orchestrator.handle_request(body.text, body.zip, body.requester_id)
