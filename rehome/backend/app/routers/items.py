"""Donor endpoints. Contract: docs/04-api-contract.md"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.agents import orchestrator
from app.core import config
from app.schemas import Item, ItemStatus, ListItemOut

router = APIRouter(prefix="/api/items", tags=["items"])
MAX_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}


@router.post("", response_model=Item, status_code=201)
async def donate_item(zip: str = Form(...), note: str | None = Form(None),
                      donor_id: str = Form("demo_donor"),
                      image: UploadFile | None = File(None)):
    note = (note or "").strip() or None
    if image is not None and not image.filename:   # empty file field from a browser form
        image = None
    if not image and not note:
        raise HTTPException(400, "Send a photo, a note, or both.")
    image_bytes, mime, url = None, "image/jpeg", None
    if image:
        mime = (image.content_type or "").lower()
        if mime not in IMAGE_TYPES:
            raise HTTPException(415, "Photo must be a JPG, PNG, or WebP image.")
        image_bytes = await image.read(MAX_BYTES + 1)
        if len(image_bytes) > MAX_BYTES:
            raise HTTPException(413, "Image is larger than 10 MB.")
    item_id = orchestrator.new_item_id()
    if image_bytes:
        name = f"{item_id}.{IMAGE_TYPES[mime]}"
        (config.UPLOAD_DIR / name).write_bytes(image_bytes)
        url = config.public_url(f"/static/uploads/{name}")
    return await orchestrator.donate(note, zip, donor_id, image_bytes, mime, url, item_id)


@router.get("")
async def list_items(status: ItemStatus | None = None):
    return {"items": orchestrator.items(status)}


@router.post("/{item_id}/list", response_model=ListItemOut)
async def list_on_marketplace(item_id: str):
    try:
        return await orchestrator.list_item(item_id)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)
