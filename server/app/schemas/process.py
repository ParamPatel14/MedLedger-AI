from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ProcessIn(BaseModel):
    text: str = Field(min_length=1)


class ValidationOut(BaseModel):
    is_valid: bool
    issues: List[Dict[str, Any]]
    confidence: float


class ProcessOut(BaseModel):
    diagnosis: List[str]
    icd_codes: List[Dict[str, Any]]
    validation: ValidationOut
    confidence: float
