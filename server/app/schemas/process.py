from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProcessIn(BaseModel):
    text: str = Field(min_length=1)


class ValidationOut(BaseModel):
    is_valid: bool
    issues: List[Dict[str, Any]]
    confidence: float


class ProcessOut(BaseModel):
    record_id: str
    diagnosis: List[str]
    procedures: List[str]
    icd_codes: List[Dict[str, Any]]
    validation: ValidationOut
    confidence: float
    explanation: Optional[Dict[str, str]] = None
