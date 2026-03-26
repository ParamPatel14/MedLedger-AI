from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_database_url


DATABASE_URL: str | None = None
engine: Engine | None = None
engine_init_error: str | None = None
SessionLocal: sessionmaker[Session] | None = None


def _init_engine() -> None:
    global DATABASE_URL, engine, engine_init_error, SessionLocal

    DATABASE_URL = get_database_url()
    engine = None
    engine_init_error = None
    SessionLocal = None

    if not DATABASE_URL:
        return

    try:
        url = make_url(DATABASE_URL)
        if url.get_backend_name() == "sqlite":
            db_path = url.database or ""
            if db_path and db_path not in (":memory:",):
                Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

        is_pgbouncer = str(url.query.get("pgbouncer", "")).lower() in ("1", "true", "yes", "on")
        if is_pgbouncer:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                echo=False,
                future=True,
                poolclass=NullPool,
            )
        else:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                echo=False,
                future=True,
            )
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    except Exception as e:
        engine = None
        SessionLocal = None
        engine_init_error = str(e)


def ensure_db_initialized() -> None:
    if SessionLocal is not None:
        return
    _init_engine()


_init_engine()


def get_db() -> Generator[Session, None, None]:
    ensure_db_initialized()
    if SessionLocal is None:
        raise RuntimeError("Database session is not initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
