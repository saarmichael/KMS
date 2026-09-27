"""Database access: one SQLAlchemy engine, plus a raw psycopg connection for LISTEN/NOTIFY.

SQLAlchemy Core is used for queries and by Alembic. LISTEN/NOTIFY needs a dedicated
autocommit connection that is not part of the pool, so it uses psycopg directly.
"""

import logging
import time
from contextlib import contextmanager
from uuid import UUID

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from kms.config import get_settings

logger = logging.getLogger(__name__)

# The queue's wake-up channel: upload and retry notify on it, the worker listens on it.
ASSET_PENDING_CHANNEL = "asset_pending"

_engine: Engine | None = None


def get_engine() -> Engine:
    """The process-wide SQLAlchemy engine, created from settings on first use."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        logger.info(
            "database_engine_created host=%s database=%s",
            _engine.url.host,
            _engine.url.database,
        )
    return _engine


def set_engine(engine: Engine | None) -> None:
    """Replace the process-wide engine; tests inject one bound to the test database.

    Args:
        engine: The engine to use from now on, or None to build one from settings on next use.
    """
    global _engine
    _engine = engine


def psycopg_dsn(url: str | None = None) -> str:
    """Turn a SQLAlchemy database URL into one that psycopg accepts.

    SQLAlchemy URLs carry a `+psycopg` driver suffix that psycopg itself does not accept.

    Args:
        url: A SQLAlchemy URL; defaults to the engine's own URL, password included.

    Returns:
        The same URL with a plain `postgresql://` scheme.
    """
    url = url or str(get_engine().url.render_as_string(hide_password=False))
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def listen_connection(channel: str):
    """Open a dedicated autocommit connection subscribed to `channel`.

    Args:
        channel: The notification channel to LISTEN on.

    Yields:
        The psycopg connection; it is closed when the `with` block ends.
    """
    with psycopg.connect(psycopg_dsn(), autocommit=True) as conn:
        conn.execute(f"LISTEN {channel}")
        yield conn


def notify_self_test(timeout_s: float = 2.0) -> dict:
    """Send a NOTIFY on a listening connection and time its arrival.

    Proves that this database delivers notifications to this process, which is the one
    platform property the queue design depends on (a transaction-mode pooler would break it).

    Args:
        timeout_s: How long to wait for the notification, in seconds.

    Returns:
        `{"ok": True, "ms": <round trip>}` when it arrives, or
        `{"ok": False, "ms": None, "error": <reason>}` when nothing arrives in time.
    """
    channel = "kms_health"
    started = time.perf_counter()
    with listen_connection(channel) as conn:
        conn.execute(f"NOTIFY {channel}, 'ping'")
        for n in conn.notifies(timeout=timeout_s):
            if n.channel == channel:
                return {"ok": True, "ms": round((time.perf_counter() - started) * 1000, 1)}
    return {"ok": False, "ms": None, "error": f"no notification within {timeout_s}s"}


def db_ping() -> bool:
    """True when the database answers `SELECT 1`; an unreachable database raises."""
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1


def notify_asset_pending(connection: Connection, asset_id: UUID) -> None:
    """Announce a pending asset inside the caller's transaction.

    Postgres delivers the notification only when that transaction commits, so a listener never
    hears about a row it cannot see yet, and a rolled-back insert announces nothing.

    Args:
        connection: The caller's connection, inside its open transaction.
        asset_id: The asset now waiting in the queue.
    """
    connection.execute(
        text("SELECT pg_notify(:channel, :asset_id)"),
        {"channel": ASSET_PENDING_CHANNEL, "asset_id": str(asset_id)},
    )
