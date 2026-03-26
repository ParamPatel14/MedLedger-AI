from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.layers.coding_layer.service import IcdCodingService, IcdMatch
from app.layers.input_layer.service import InputIngestionService
from app.layers.processing_layer.service import ClinicalNlpService, NormalizedEntity
from app.layers.storage_layer.service import StorageService
from app.schemas.pipeline import CodeOut, EntityOut, ExtractOut, RecordOut, TextUploadIn
from app.services.gemini import extract_with_gemini, ocr_with_gemini


router = APIRouter(tags=["pipeline"])

_ingest = InputIngestionService()
_nlp = ClinicalNlpService()
_coder = IcdCodingService()
_storage = StorageService()


def _entities_to_out(entities: List[NormalizedEntity]) -> List[EntityOut]:
    out: List[EntityOut] = []
    for e in entities:
        out.append(
            EntityOut(
                type=e.type,
                value=e.value,
                normalized_value=e.normalized_value,
                ontology_id=e.ontology_id or None,
                start=e.start,
                end=e.end,
                confidence=e.confidence,
            )
        )
    return out


def _codes_to_out(codes: List[IcdMatch]) -> List[CodeOut]:
    out: List[CodeOut] = []
    for c in codes:
        out.append(
            CodeOut(
                system="ICD10",
                code=c.code,
                description=c.description,
                confidence=c.confidence,
                source_text=c.source_text,
            )
        )
    return out


def _build_record_out(record, entities: List[NormalizedEntity], codes: List[IcdMatch], extracted: ExtractOut) -> RecordOut:
    return RecordOut(
        id=record.id,
        filename=record.filename,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        text=record.raw_text,
        extracted=extracted,
        codes=_codes_to_out(codes),
        created_at=record.created_at,
        nlp_model=record.nlp_model,
        nlp_model_version=record.nlp_model_version,
        icd_dataset_version=record.icd_dataset_version,
        icd_embed_model=record.icd_embed_model,
    )


def _nlp_version() -> str:
    try:
        import spacy

        return f"spacy:{spacy.__version__}"
    except Exception:
        return ""


def _run_pipeline(db: Session, *, source: str, filename: str, content_type: str, size_bytes: int, text: str) -> RecordOut:
    cleaned, entities = _nlp.extract(text)
    diagnosis, procedures, medications = _nlp.summarize(entities)

    if not diagnosis and not procedures and not medications:
        fallback = extract_with_gemini(cleaned)
        if fallback is not None:
            diagnosis = fallback.diagnosis
            procedures = fallback.procedures
            medications = fallback.medications

    codes: List[IcdMatch] = []
    seen_codes = set()
    for d in diagnosis:
        matches = _coder.match_diagnosis(d, top_k=1)
        for m in matches:
            key = (m.code, m.description)
            if key in seen_codes:
                continue
            seen_codes.add(key)
            codes.append(m)

    extracted = ExtractOut(
        diagnosis=diagnosis,
        procedures=procedures,
        medications=medications,
        entities=_entities_to_out(entities),
    )

    record = _storage.create_record(
        db,
        source=source,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        raw_text=cleaned,
        nlp_model=_nlp.model_name,
        nlp_model_version=_nlp_version(),
        icd_dataset_version=_coder.dataset_version,
        icd_embed_model=_coder.embed_model,
        entities=entities,
        codes=codes,
        audit_details={"source": source},
    )

    return _build_record_out(record, entities, codes, extracted)


@router.post("/upload", response_model=RecordOut)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)) -> RecordOut:
    raw = await file.read()
    doc = _ingest.ingest_upload(file, raw)
    return _run_pipeline(
        db,
        source="upload",
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        text=doc.text,
    )


@router.post("/upload/text", response_model=RecordOut)
def upload_text(payload: TextUploadIn, db: Session = Depends(get_db)) -> RecordOut:
    return _run_pipeline(
        db,
        source="text",
        filename="",
        content_type="text/plain",
        size_bytes=len(payload.text.encode("utf-8", errors="ignore")),
        text=payload.text,
    )


@router.post("/upload/handwritten", response_model=RecordOut)
async def upload_handwritten(file: UploadFile = File(...), db: Session = Depends(get_db)) -> RecordOut:
    raw = await file.read()
    content_type = file.content_type or "application/octet-stream"
    if not (content_type.startswith("image/") or content_type == "application/pdf"):
        raise HTTPException(status_code=400, detail="Unsupported file type for handwritten upload")
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=400, detail="GEMINI_API_KEY is not configured on the server")

    text = ocr_with_gemini(raw, content_type)
    if text is None:
        raise HTTPException(status_code=502, detail="Handwritten OCR failed")

    return _run_pipeline(
        db,
        source="handwritten",
        filename=file.filename or "",
        content_type=content_type,
        size_bytes=len(raw),
        text=text,
    )


@router.get("/results/{record_id}", response_model=RecordOut)
def get_results(record_id: str, db: Session = Depends(get_db)) -> RecordOut:
    record = _storage.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")

    entity_rows = _storage.list_entities(db, record_id)
    entities: List[NormalizedEntity] = []
    for row in entity_rows:
        entities.append(
            NormalizedEntity(
                type=row.type,
                value=row.value,
                normalized_value=row.normalized_value,
                ontology_id=row.ontology_id,
                start=row.start,
                end=row.end,
                confidence=row.confidence,
            )
        )

    code_rows = _storage.list_codes(db, record_id)
    codes: List[IcdMatch] = []
    for row in code_rows:
        codes.append(
            IcdMatch(
                code=row.code,
                description=row.description,
                confidence=row.confidence,
                method="stored",
                source_text=row.source_text,
            )
        )

    diagnosis, procedures, medications = _nlp.summarize(entities)
    extracted = ExtractOut(
        diagnosis=diagnosis,
        procedures=procedures,
        medications=medications,
        entities=_entities_to_out(entities),
    )
    return _build_record_out(record, entities, codes, extracted)
