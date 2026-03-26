from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, UploadFile

from app.services import parser


@dataclass(frozen=True)
class IngestedDocument:
    filename: str
    content_type: str
    size_bytes: int
    text: str
    temp_file_id: str


class InputIngestionService:
    def ingest_upload(self, file: UploadFile, raw: bytes) -> IngestedDocument:
        if file is None:
            raise HTTPException(status_code=400, detail="Missing file")
        text, size_bytes, content_type = parser.extract_text(file, raw)
        temp_id = parser.save_temp_file(file, raw)
        return IngestedDocument(
            filename=file.filename or "",
            content_type=content_type,
            size_bytes=size_bytes,
            text=text,
            temp_file_id=temp_id,
        )
