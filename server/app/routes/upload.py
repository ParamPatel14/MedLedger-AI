from fastapi import APIRouter, File, UploadFile

from app.models.schemas import ProcessResponse, UploadResponse
import app.services.parser as parser
from app.services.nlp import pipeline

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    raw = await file.read()
    text, size_bytes, content_type = parser.extract_text(file, raw)
    file_id = parser.save_temp_file(file, raw)
    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "",
        content_type=content_type,
        size_bytes=size_bytes,
        text=text,
    )


@router.post("/upload/process", response_model=ProcessResponse)
async def upload_and_process(file: UploadFile = File(...)) -> ProcessResponse:
    raw = await file.read()
    text, _, _ = parser.extract_text(file, raw)
    parser.save_temp_file(file, raw)
    return pipeline.process(text, include_entities=True)
