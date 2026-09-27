"""Run and inspect Alembic migrations from Python (container start, tests, health)."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


def alembic_config(database_url: str) -> Config:
    """Build an Alembic config for this project's migrations and the given database.

    Args:
        database_url: The database to migrate, handed to env.py as `-x database_url=...`.

    Returns:
        The Alembic config.
    """
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"database_url={database_url}"]})()
    return cfg


def upgrade_head(database_url: str) -> None:
    """Apply every pending migration to the database at `database_url`."""
    command.upgrade(alembic_config(database_url), "head")
    logger.info("migrations_applied revision=%s", head_revision(database_url))


def head_revision(database_url: str) -> str | None:
    """The newest revision among the migration scripts; None if there are none."""
    return ScriptDirectory.from_config(alembic_config(database_url)).get_current_head()


def current_revision(engine: Engine) -> str | None:
    """The revision the database is at; None if it was never migrated or cannot be read."""
    with engine.connect() as conn:
        try:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except Exception:
            return None
