from fastapi import APIRouter

from app.api.routes import denial, health, nlp, pipeline, process


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(nlp.router)
api_router.include_router(pipeline.router)
api_router.include_router(process.router)
api_router.include_router(denial.router)

