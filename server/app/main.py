from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.logging import configure_logging

import app.api.routes.health as health_routes
import app.routes.nlp as nlp_routes
import app.routes.upload as upload_routes


def create_app() -> FastAPI:
    configure_logging()
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

    app.include_router(health_routes.router)
    app.include_router(upload_routes.router)
    app.include_router(nlp_routes.router)

    return app


app = create_app()
