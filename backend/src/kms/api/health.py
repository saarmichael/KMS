import logging

from fastapi import APIRouter

from kms import db, migrations
from kms.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    """Answer 'is this deployment sound' in one call.

    Checks that the DB is reachable, the schema is current, and LISTEN/NOTIFY is delivered on
    this connection (the queue's wake-up mechanism).

    Returns:
        Each check's result, and a `status` of "ok", or "degraded" when any check fails.
    """
    engine = db.get_engine()
    url = engine.url.render_as_string(hide_password=False)
    report: dict = {"status": "ok"}
    try:
        report["db"] = "ok" if db.db_ping() else "bad"
    except Exception as error:  # pragma: no cover - surfaced in the response
        report["db"] = f"error: {error}"
        report["status"] = "degraded"
        logger.warning("health_degraded db=%r", report["db"])
        return report
    current, head = migrations.current_revision(engine), migrations.head_revision(url)
    report["migrations"] = {"current": current, "head": head, "ok": current == head}
    report["notify"] = db.notify_self_test()
    report["ai_provider"] = get_settings().ai_provider
    if not (report["migrations"]["ok"] and report["notify"]["ok"]):
        report["status"] = "degraded"
        logger.warning(
            "health_degraded migrations_current=%s migrations_head=%s notify=%s",
            current,
            head,
            report["notify"],
        )
    return report
