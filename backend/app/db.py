import os
from collections.abc import Iterator

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, create_engine, event, text
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

# JSONB on Postgres (flexible, document-style triage notes), plain JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(TypeDecorator):
    """Stores UTC; always returns timezone-aware UTC datetimes (SQLite drops tzinfo otherwise)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


def normalize_db_url(url: str) -> str:
    """Hosted Postgres (Render, Heroku) hands out postgres:// URLs; SQLAlchemy + psycopg3 needs postgresql+psycopg://."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _make_engine():
    url = normalize_db_url(get_settings().database_url)
    if url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _fk(dbapi_conn, _):  # pragma: no cover - sqlite pragma
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return eng
    # Neon (serverless Postgres) suspends idle compute and may drop idle connections:
    # check connections before use and recycle them well inside its idle window.
    return create_engine(url, pool_pre_ping=True, pool_recycle=240, pool_size=5, max_overflow=5, pool_timeout=30)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION jeevia_audit_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS audit_no_update ON audit_events;
CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION jeevia_audit_append_only();
"""


def _alembic_config(connection):
    from pathlib import Path

    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    cfg.attributes["configure_logger"] = False
    cfg.attributes["connection"] = connection
    return cfg


def _add_missing_columns() -> None:
    """SQLite has no migrations here and create_all never alters an existing table, so a local demo database made
    before a column was added would fail on the first query. Add any missing nullable column in place."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have and col.nullable:
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(engine.dialect)}'))


def init_db() -> None:
    """Bring the schema to the latest version.

    PostgreSQL: Alembic migrations (a database created before migrations existed is stamped at
    the baseline first). SQLite (tests, quick local runs): create tables directly.
    """
    from . import models  # noqa: F401  (register tables)

    if engine.dialect.name != "postgresql":
        Base.metadata.create_all(engine)
        _add_missing_columns()
        return

    from alembic import command
    from sqlalchemy import inspect

    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(7274422)"))  # one migrator at a time
        cfg = _alembic_config(conn)
        tables = set(inspect(conn).get_table_names())
        if "alembic_version" not in tables and "facilities" in tables:
            command.stamp(cfg, "0001")
        command.upgrade(cfg, "head")
        conn.execute(text(APPEND_ONLY_SQL))
