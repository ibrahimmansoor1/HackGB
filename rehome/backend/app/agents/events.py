"""Activity feed logger. Every agent step calls emit().
`event_type` is set only on steps the impact dashboard counts (docs/05)."""
from app.core import db


def emit(agent: str, message: str, item_id: str | None = None,
         request_id: str | None = None, event_type: str | None = None,
         category: str | None = None) -> None:
    db.insert_event({"agent": agent, "message": message, "item_id": item_id,
                     "request_id": request_id, "event_type": event_type,
                     "category": category, "created_at": db.now()})
