from typing import Any, Dict

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import DATABASE_URL, engine, engine_init_error


router = APIRouter()


@router.get("/")
def read_root() -> Dict[str, Any]:
    return {"message": "Hello FastAPI 🚀"}


@router.get("/hello/{name}")
def say_hello(name: str) -> Dict[str, Any]:
    return {"message": f"Hello {name}"}


@router.get("/db/health")
def db_health() -> Dict[str, Any]:
    if not DATABASE_URL:
        return {
            "ok": False,
            "status": "missing_database_url",
            "detail": "DATABASE_URL is not set in environment",
        }
    if engine is None:
        message = engine_init_error or "Failed to initialize database engine"
        if "No module named" in message:
            return {"ok": False, "status": "driver_missing", "detail": message}
        return {"ok": False, "status": "engine_init_failed", "detail": message}
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
        return {"ok": True, "status": "up", "result": result}
    except Exception as e:
        message = str(e)
        if "could not translate host name" in message or "No such host is known" in message:
            return {
                "ok": False,
                "status": "dns_error",
                "error": message,
                "detail": "DNS could not resolve the database hostname from this machine/network.",
            }
        return {"ok": False, "status": "down", "error": message}

