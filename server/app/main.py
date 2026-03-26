import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

engine = None
engine_init_error = None
if DATABASE_URL:
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        from sqlalchemy.pool import NullPool

        url = make_url(DATABASE_URL)
        connect_args = {}

        is_pgbouncer = str(url.query.get("pgbouncer", "")).lower() in ("1", "true", "yes", "on")
        if is_pgbouncer:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                echo=False,
                future=True,
                poolclass=NullPool,
                connect_args=connect_args,
            )
        else:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                echo=False,
                future=True,
                connect_args=connect_args,
            )
    except Exception as e:
        engine_init_error = str(e)
        engine = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello FastAPI 🚀"}

@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"Hello {name}"}

@app.get("/db/health")
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
            return {
                "ok": False,
                "status": "driver_missing",
                "detail": message,
            }
        return {"ok": False, "status": "engine_init_failed", "detail": message}
    try:
        from sqlalchemy import text
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
