"""Donor endpoints. Contract: docs/04-api-contract.md"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.agents import orchestrator
from app.core import config, db
from app.schemas import Item, ListItemOut

router = APIRouter(prefix="/api/items", tags=["items"])
MAX_BYTES = 10 * 1024 * 1024


@router.post("", response_model=Item, status_code=201)
async def donate_item(zip: str = Form(...), note: str | None = Form(None),
                      donor_id: str = Form("demo_donor"),
                      image: UploadFile | None = File(None)):
    if not image and not note:
        raise HTTPException(400, "Send a photo, a note, or both.")
    item_id = db.new_item_id()
    image_bytes, mime, url = None, "image/jpeg", None
    if image:
        image_bytes = await image.read()
        if len(image_bytes) > MAX_BYTES:
            raise HTTPException(413, "Image is larger than 10 MB.")
        mime = image.content_type or mime
        ext = mime.split("/")[-1]
        (config.UPLOAD_DIR / f"{item_id}.{ext}").write_bytes(image_bytes)
        url = f"/static/uploads/{item_id}.{ext}"
    return await orchestrator.donate(note, zip, donor_id, image_bytes, mime, url, item_id)


@router.get("")
async def list_items(status: str | None = None):
    return {"items": [orchestrator._public(r) for r in db.list_items(status)]}


@router.post("/{item_id}/list", response_model=ListItemOut)
async def list_on_marketplace(item_id: str):
    try:
        return await orchestrator.list_item(item_id)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)
