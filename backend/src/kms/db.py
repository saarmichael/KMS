"""Database access: one SQLAlchemy engine, plus a raw psycopg connection for LISTEN/NOTIFY.

SQLAlchemy Core is used for queries and by Alembic. LISTEN/NOTIFY needs a dedicated
autocommit connection that is not part of the pool, so it uses psycopg directly.
"""

import time
from contextlib import contextmanager

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from kms.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def set_engine(engine: Engine | None) -> None:
    """Tests inject an engine bound to the test database."""
    global _engine
    _engine = engine


def psycopg_dsn(url: str | None = None) -> str:
    """SQLAlchemy URLs carry a `+psycopg` driver suffix that psycopg itself does not accept."""
    url = url or str(get_engine().url.render_as_string(hide_password=False))
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def listen_connection(channel: str):
    """A dedicated autocommit connection subscribed to `channel`."""
    with psycopg.connect(psycopg_dsn(), autocommit=True) as conn:
        conn.execute(f"LISTEN {channel}")
        yield conn


def notify_self_test(timeout_s: float = 2.0) -> dict:
    """Send a NOTIFY on a listening connection and time its arrival.

    Proves that this database delivers notifications to this process, which is the one
    platform property the queue design depends on (a transaction-mode pooler would break it).
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
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1
