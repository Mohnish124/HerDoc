from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL as _SQLA_URL

from app.config import get_settings
from app.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL

target_metadata = Base.metadata


def _get_url() -> str:
    if isinstance(DATABASE_URL, _SQLA_URL):
        return DATABASE_URL.render_as_string(hide_password=False)
    return str(DATABASE_URL)


def _set_safe_url_option() -> None:
    raw = _get_url()
    ini_safe = raw.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", ini_safe)


_set_safe_url_option()


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {}) or {}
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=_get_url(),
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
