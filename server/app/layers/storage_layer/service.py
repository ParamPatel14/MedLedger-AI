from __future__ import annotations

import json
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.layers.coding_layer.service import IcdMatch
from app.layers.processing_layer.service import NormalizedEntity
from app.models.audit import AuditLog
from app.models.code import ClinicalCode
from app.models.entity import ClinicalEntity
from app.models.record import ClinicalRecord


class StorageService:
    def create_record(
        self,
        db: Session,
        *,
        source: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        raw_text: str,
        nlp_model: str,
        nlp_model_version: str,
        icd_dataset_version: str,
        icd_embed_model: str,
        entities: Iterable[NormalizedEntity],
        codes: Iterable[IcdMatch],
        audit_details: Optional[dict] = None,
    ) -> ClinicalRecord:
        rec = ClinicalRecord(
            source=source,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            raw_text=raw_text,
            nlp_model=nlp_model,
            nlp_model_version=nlp_model_version,
            icd_dataset_version=icd_dataset_version,
            icd_embed_model=icd_embed_model,
        )
        db.add(rec)
        db.flush()

        for e in entities:
            db.add(
                ClinicalEntity(
                    record_id=rec.id,
                    type=e.type,
                    value=e.value,
                    normalized_value=e.normalized_value,
                    ontology_id=e.ontology_id,
                    start=e.start,
                    end=e.end,
                    confidence=e.confidence,
                )
            )

        for c in codes:
            db.add(
                ClinicalCode(
                    record_id=rec.id,
                    system="ICD10",
                    code=c.code,
                    description=c.description,
                    confidence=c.confidence,
                    source_text=c.source_text,
                )
            )

        if audit_details is not None:
            db.add(
                AuditLog(
                    record_id=rec.id,
                    action="record.created",
                    details=json.dumps(audit_details, ensure_ascii=False),
                )
            )

        db.commit()
        db.refresh(rec)
        return rec

    def get_record(self, db: Session, record_id: str) -> Optional[ClinicalRecord]:
        return db.get(ClinicalRecord, record_id)

    def list_entities(self, db: Session, record_id: str) -> List[ClinicalEntity]:
        return (
            db.query(ClinicalEntity)
            .filter(ClinicalEntity.record_id == record_id)
            .order_by(ClinicalEntity.id.asc())
            .all()
        )

    def list_codes(self, db: Session, record_id: str) -> List[ClinicalCode]:
        return (
            db.query(ClinicalCode)
            .filter(ClinicalCode.record_id == record_id)
            .order_by(ClinicalCode.id.asc())
            .all()
        )
