from __future__ import annotations

import logging
import io
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile


logger = logging.getLogger("app.services.parser")


def _clean_text(text: str) -> str:
    text = text.replace("\u0000", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _uploads_dir() -> Path:
    base = Path.cwd() / ".tmp" / "uploads"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_temp_file(file: UploadFile, raw: bytes) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    file_id = uuid.uuid4().hex
    path = _uploads_dir() / f"{file_id}{suffix}"
    path.write_bytes(raw)
    return file_id


def extract_text(file: UploadFile, raw: bytes) -> tuple[str, int, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content_type = (file.content_type or "").lower()
    name_lower = file.filename.lower()
    if not raw:
        raise HTTPException(status_code=400, detail="File is empty")

    if content_type in {"text/plain"} or name_lower.endswith(".txt"):
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = raw.decode(errors="replace")
        cleaned = _clean_text(text)
        if not cleaned:
            raise HTTPException(status_code=400, detail="File contained no readable text")
        return cleaned, len(raw), content_type or "text/plain"

    if content_type in {"application/pdf"} or name_lower.endswith(".pdf"):
        text = ""
        try:
            import fitz

            doc = fitz.open(stream=raw, filetype="pdf")
            pages = []
            for page in doc:
                pages.append(page.get_text("text"))
            text = "\n".join(pages)
        except Exception:
            try:
                import pdfplumber

                with pdfplumber.open(io.BytesIO(raw)) as pdf:
                    pages = []
                    for page in pdf.pages:
                        pages.append(page.extract_text() or "")
                    text = "\n".join(pages)
            except Exception as e:
                logger.exception("PDF text extraction failed")
                raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {e}")

        cleaned = _clean_text(text)
        if not cleaned:
            raise HTTPException(status_code=400, detail="PDF contained no extractable text")
        return cleaned, len(raw), content_type or "application/pdf"

    raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or TXT.")


def extract_text_from_upload(file: UploadFile) -> tuple[str, int, str]:
    raw = file.file.read()
    return extract_text(file, raw)
