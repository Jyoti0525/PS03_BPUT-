"""Alembic environment. The database URL comes from JEEVIA_DATABASE_URL (same as the app)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401  (register tables)
from app.config import get_settings
from app.db import Base, normalize_db_url

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

config.set_main_option("sqlalchemy.url", normalize_db_url(get_settings().database_url).replace("%", "%%"))
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Hand-written expression indexes (e.g. the trigram search index) are managed in migrations only.
    return not (type_ == "index" and name and name.endswith("_trgm"))


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, compare_type=True, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, include_object=include_object, render_as_batch=connection.dialect.name == "sqlite")
            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(connection=connectable, target_metadata=target_metadata, compare_type=True, include_object=include_object, render_as_batch=connectable.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
