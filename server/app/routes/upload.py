import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import ProcessResponse, UploadResponse
import app.services.parser as parser
from app.services.gemini import ocr_with_gemini
from app.services.pipeline import pipeline

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


@router.post("/upload/handwritten", response_model=UploadResponse)
async def upload_handwritten(file: UploadFile = File(...)) -> UploadResponse:
    raw = await file.read()
    content_type = file.content_type or "application/octet-stream"
    if not (content_type.startswith("image/") or content_type == "application/pdf"):
        raise HTTPException(status_code=400, detail="Unsupported file type for handwritten upload")

    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY is not configured on the server")

    text = ocr_with_gemini(raw, content_type)
    if text is None:
        raise HTTPException(status_code=502, detail="Handwritten OCR failed")

    file_id = parser.save_temp_file(file, raw)
    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "",
        content_type=content_type,
        size_bytes=len(raw),
        text=text,
    )
