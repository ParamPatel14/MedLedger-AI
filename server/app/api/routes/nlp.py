from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.term import ClinicalTerm
from app.schemas.nlp import NlpExtractRequest, NlpExtractResponse, TermOut, TermUpsert
from app.services.nlp.extractor import extract_entities


router = APIRouter(prefix="/nlp", tags=["nlp"])


@router.post("/extract", response_model=NlpExtractResponse)
def nlp_extract(payload: NlpExtractRequest, db: Session = Depends(get_db)) -> NlpExtractResponse:
    return extract_entities(db, payload.text)


@router.get("/terms", response_model=List[TermOut])
def list_terms(db: Session = Depends(get_db)) -> List[TermOut]:
    rows = db.execute(select(ClinicalTerm).order_by(ClinicalTerm.type.asc(), ClinicalTerm.canonical.asc())).scalars().all()
    out: List[TermOut] = []
    for row in rows:
        synonyms = [s.strip() for s in (row.synonyms or "").replace("|", "\n").splitlines() if s.strip()]
        out.append(
            TermOut(
                id=row.id,
                type=row.type,
                canonical=row.canonical,
                synonyms=synonyms,
                enabled=row.enabled,
            )
        )
    return out


@router.post("/terms/import", response_model=List[TermOut])
def import_terms(payload: List[TermUpsert], db: Session = Depends(get_db)) -> List[TermOut]:
    for item in payload:
        canonical = item.canonical.strip().lower()
        synonyms = item.synonyms or []
        synonyms_clean = [s.strip() for s in synonyms if s and s.strip()]
        synonyms_blob = "\n".join(dict.fromkeys(synonyms_clean))

        existing = (
            db.execute(
                select(ClinicalTerm).where(
                    ClinicalTerm.type == item.type,
                    ClinicalTerm.canonical == canonical,
                )
            )
            .scalars()
            .first()
        )
        if existing is None:
            db.add(
                ClinicalTerm(
                    type=item.type,
                    canonical=canonical,
                    synonyms=synonyms_blob,
                    enabled=item.enabled,
                )
            )
        else:
            existing.synonyms = synonyms_blob
            existing.enabled = item.enabled

    db.commit()
    return list_terms(db)

