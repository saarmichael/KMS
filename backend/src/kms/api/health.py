from fastapi import APIRouter

from kms import db, migrations
from kms.config import get_settings

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    """One call that answers 'is this deployment sound': DB reachable, schema current,
    and LISTEN/NOTIFY delivered on this connection (the queue's wake-up mechanism)."""
    engine = db.get_engine()
    url = engine.url.render_as_string(hide_password=False)
    out: dict = {"status": "ok"}
    try:
        out["db"] = "ok" if db.db_ping() else "bad"
    except Exception as e:  # pragma: no cover - surfaced in the response
        out["db"] = f"error: {e}"
        out["status"] = "degraded"
        return out
    current, head = migrations.current_revision(engine), migrations.head_revision(url)
    out["migrations"] = {"current": current, "head": head, "ok": current == head}
    out["notify"] = db.notify_self_test()
    out["ai_provider"] = get_settings().ai_provider
    if not (out["migrations"]["ok"] and out["notify"]["ok"]):
        out["status"] = "degraded"
    return out
