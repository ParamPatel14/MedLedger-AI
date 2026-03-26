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

engine = None
if DATABASE_URL:
    try:
        from sqlalchemy import create_engine
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False, future=True)
    except Exception:
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
        return {
            "ok": False,
            "status": "engine_init_failed",
            "detail": "Failed to initialize database engine (driver may be missing)",
        }
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
