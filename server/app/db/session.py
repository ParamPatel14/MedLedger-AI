from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_database_url


DATABASE_URL = get_database_url()

engine: Engine | None = None
engine_init_error: str | None = None
SessionLocal: sessionmaker[Session] | None = None

if DATABASE_URL:
    try:
        url = make_url(DATABASE_URL)
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


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("Database session is not initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

