"""Activity feed logger. Every agent step calls emit().
`event_type` is set only on steps the impact dashboard counts (docs/05).
`run_id`, `tool`, `duration_ms` and `data` trace agent runs (the concierge)."""
from contextvars import ContextVar

from app.core import db

# Set while an agent run is in progress; every emit() inside it (including the
# orchestrator and specialist agents the run calls) is tagged with this run_id.
current_run: ContextVar[str | None] = ContextVar("current_run", default=None)


def emit(agent: str, message: str, item_id: str | None = None,
         request_id: str | None = None, event_type: str | None = None,
         category: str | None = None, run_id: str | None = None,
         tool: str | None = None, duration_ms: int | None = None,
         data: dict | None = None) -> None:
    db.insert_event({"agent": agent, "message": message, "item_id": item_id,
                     "request_id": request_id, "event_type": event_type,
                     "category": category, "run_id": run_id or current_run.get(), "tool": tool,
                     "duration_ms": duration_ms, "data": data, "created_at": db.now()})
