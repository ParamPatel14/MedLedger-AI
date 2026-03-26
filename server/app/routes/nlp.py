from fastapi import APIRouter

from app.models.schemas import ProcessRequest, ProcessResponse
from app.services.pipeline import pipeline


router = APIRouter()


@router.post("/process", response_model=ProcessResponse)
def process(payload: ProcessRequest) -> ProcessResponse:
    return pipeline.process(payload.text, include_entities=True)

