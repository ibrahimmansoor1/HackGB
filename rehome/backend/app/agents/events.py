"""Activity feed logger. Every agent step calls emit()."""
from app.core import db


def emit(agent: str, message: str, item_id: str | None = None,
         request_id: str | None = None) -> None:
    db.insert_event({"agent": agent, "message": message, "item_id": item_id,
                     "request_id": request_id, "created_at": db.now()})
