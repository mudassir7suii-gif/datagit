from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datagit.config import settings
from datagit.storage.models import Base

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


import os
from sqlalchemy import create_engine

def get_database_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("DATAGIT_DATABASE_URL")
    if not url:
        x_url = context.get_x_argument(as_dictionary=True).get("url")
        if x_url:
            url = x_url
    if not url:
        cfg_url = config.get_main_option("sqlalchemy.url")
        if cfg_url and not cfg_url.startswith("driver://"):
            url = cfg_url
    if not url:
        url = settings.database_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        try:
            import psycopg  # noqa: F401
        except ImportError:
            try:
                import psycopg2  # noqa: F401
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            except ImportError:
                pass
    return url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    is_sqlite = url.startswith("sqlite")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_database_url()
    is_sqlite = url.startswith("sqlite")
    connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    connectable = create_engine(url, connect_args=connect_args)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
