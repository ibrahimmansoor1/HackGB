"""Donor endpoints. Contract: docs/04-api-contract.md"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.agents import concierge, orchestrator
from app.core import config
from app.schemas import (DonateIn, DonateOut, DraftOut, HandleIn, HandleOut, Item, ItemStatus,
                         ListIn, ListItemOut, PostIn, SellOut)

router = APIRouter(prefix="/api/items", tags=["items"])
MAX_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}


async def _read_images(files: list[UploadFile]) -> list[tuple[bytes, str]]:
    """Validate uploads -> [(bytes, mime)]. Empty browser file fields are skipped."""
    out = []
    for f in files:
        if not f.filename:
            continue
        mime = (f.content_type or "").lower()
        if mime not in IMAGE_TYPES:
            raise HTTPException(415, "Photo must be a JPG, PNG, or WebP image.")
        data = await f.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Image is larger than 10 MB.")
        if data:
            out.append((data, mime))
    return out


def _save_first(images: list[tuple[bytes, str]], name: str) -> str | None:
    """Save the first photo as static/uploads/<name>.<ext>; return its URL."""
    if not images:
        return None
    data, mime = images[0]
    filename = f"{name}.{IMAGE_TYPES[mime]}"
    (config.UPLOAD_DIR / filename).write_bytes(data)
    return config.public_url(f"/static/uploads/{filename}")


@router.post("/parse", response_model=DraftOut, status_code=201)
async def parse_item(zip: str = Form(...), text: str | None = Form(None),
                     donor_id: str = Form("demo_donor"),
                     images: list[UploadFile] | None = File(None)):
    text = (text or "").strip() or None
    photos = await _read_images(images or [])
    if not photos and not text:
        raise HTTPException(400, "Send a photo, a description, or both.")
    draft_id = orchestrator.new_draft_id()
    try:
        return await orchestrator.parse_draft(text, zip, donor_id, photos,
                                              _save_first(photos, draft_id), draft_id)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)


@router.post("/{draft_id}/sell", response_model=SellOut)
async def sell_draft(draft_id: str):
    try:
        return await orchestrator.sell_draft(draft_id)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)


@router.post("/{draft_id}/handle", response_model=HandleOut)
async def handle_draft(draft_id: str, body: HandleIn | None = None):
    """Hand the draft to the concierge agent: it prices it, checks local demand,
    then lists or donates it, and says what it did."""
    try:
        return await concierge.handle(draft_id, body.preference if body else "auto")
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)


@router.post("/{draft_id}/post", response_model=ListItemOut, status_code=201)
async def post_draft(draft_id: str, body: PostIn | None = None):
    try:
        return await orchestrator.post_draft(draft_id, body.price if body else None)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)


@router.post("/{draft_id}/donate", response_model=DonateOut, status_code=201)
async def donate_draft(draft_id: str, body: DonateIn | None = None):
    try:
        return await orchestrator.donate_draft(draft_id, body.pickup_zip if body else None)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)


@router.post("", response_model=Item, status_code=201)
async def donate_item(zip: str = Form(...), note: str | None = Form(None),
                      donor_id: str = Form("demo_donor"),
                      image: UploadFile | None = File(None)):
    """Legacy one-step donate; remove once the frontend uses /parse + /donate."""
    note = (note or "").strip() or None
    if image is not None and not image.filename:   # empty file field from a browser form
        image = None
    if not image and not note:
        raise HTTPException(400, "Send a photo, a note, or both.")
    photos = await _read_images([image] if image else [])
    if not photos and not note:
        raise HTTPException(400, "The photo is empty. Send a photo, a note, or both.")
    item_id = orchestrator.new_item_id()
    data, mime = photos[0] if photos else (None, "image/jpeg")
    try:
        return await orchestrator.donate(note, zip, donor_id, data, mime,
                                         _save_first(photos, item_id), item_id)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)


@router.get("")
async def list_items(status: ItemStatus | None = None):
    return {"items": orchestrator.items(status)}


@router.post("/{item_id}/list", response_model=ListItemOut)
async def list_on_marketplace(item_id: str, body: ListIn | None = None):
    """List an available item at an optional price. Drafts use /{draft_id}/post."""
    try:
        return await orchestrator.list_item(item_id, price=body.price if body else None)
    except orchestrator.FlowError as e:
        raise HTTPException(e.status_code, e.detail)
