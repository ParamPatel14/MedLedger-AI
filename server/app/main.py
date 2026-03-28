from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from app.utils.logging import configure_logging

from app.api.router import api_router
import app.routes.nlp as nlp_routes
import app.routes.upload as upload_routes
from app.db.init_db import init_db


def create_app() -> FastAPI:
    load_dotenv(override=False)
    configure_logging()
    app = FastAPI()

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(upload_routes.router)
    app.include_router(nlp_routes.router)

    return app


app = create_app()
