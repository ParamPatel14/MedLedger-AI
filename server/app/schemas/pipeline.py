from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


EntityType = Literal["diagnosis", "procedure", "medication"]


class EntityOut(BaseModel):
    type: EntityType
    value: str
    normalized_value: Optional[str] = None
    ontology_id: Optional[str] = None
    start: int
    end: int
    confidence: float


class CodeOut(BaseModel):
    system: str = "ICD10"
    code: str
    description: str
    confidence: float
    source_text: str


class ExtractOut(BaseModel):
    diagnosis: List[str]
    procedures: List[str]
    medications: List[str]
    entities: List[EntityOut]


class RecordOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    text: str
    extracted: ExtractOut
    codes: List[CodeOut]
    created_at: datetime
    nlp_model: str
    nlp_model_version: str
    icd_dataset_version: str
    icd_embed_model: str


class TextUploadIn(BaseModel):
    text: str = Field(min_length=1)
