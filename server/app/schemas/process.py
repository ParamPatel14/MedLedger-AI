from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ProcessIn(BaseModel):
    text: str = Field(min_length=1)


class ValidationOut(BaseModel):
    is_valid: bool
    issues: List[Dict[str, Any]]
    confidence: float


class SvmResultOut(BaseModel):
    status: str
    confidence: float
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    claims: List[Dict[str, Any]] = Field(default_factory=list)
    explanations: List[str] = Field(default_factory=list)
    scores: Dict[str, float] = Field(default_factory=dict)
    decision: Dict[str, Any] = Field(default_factory=dict)


class ProcessOut(BaseModel):
    status: str
    diagnosis: List[str]
    icd_codes: List[Dict[str, Any]]
    validation: ValidationOut
    confidence: float
    svm: Dict[str, SvmResultOut] = Field(default_factory=dict)


class AgentFlowStepOut(BaseModel):
    agent: str
    status: str


class ClinicalAgentOut(BaseModel):
    diagnosis: List[str]
    procedures: List[str]
    confidence: float
    explanation: str


class CodingAgentOut(BaseModel):
    icd_codes: List[Dict[str, Any]]
    mapping_reason: str
    confidence: float


class PayerAgentOut(BaseModel):
    is_valid: bool
    issues: List[Dict[str, Any]]
    confidence: float


class ProcessTraceOut(BaseModel):
    record_id: str
    flow: List[AgentFlowStepOut]
    clinical: ClinicalAgentOut
    coding: CodingAgentOut
    payer: PayerAgentOut
    confidence: float
    status: str
    svm: Dict[str, SvmResultOut] = Field(default_factory=dict)
