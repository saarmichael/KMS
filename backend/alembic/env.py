"""Alembic environment: URL from settings, metadata from kms.models."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from kms.config import get_settings
from kms.models import metadata as target_metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -x database_url=... overrides (used by the test suite); otherwise settings.
url = context.get_x_argument(as_dictionary=True).get("database_url") or get_settings().database_url
config.set_main_option("sqlalchemy.url", url)


def run_migrations_offline() -> None:
    """Emit the migrations as SQL, without connecting to the database."""
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply the migrations over a live connection to the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
