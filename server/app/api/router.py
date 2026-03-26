from fastapi import APIRouter

from app.api.routes import health, nlp, pipeline


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(nlp.router)
api_router.include_router(pipeline.router)

