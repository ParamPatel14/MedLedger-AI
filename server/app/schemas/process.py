from __future__ import annotations

from typing import Any, Dict, List, Optional

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


class GovernanceOut(BaseModel):
    decision: str
    confidence: float
    reason: str = ""
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    audit_id: str = ""
    refusal: Dict[str, Any] | None = None
    escalation: Dict[str, Any] | None = None


class ProcessOut(BaseModel):
    status: str
    decision: str
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    audit_id: str = ""
    diagnosis: List[str]
    icd_codes: List[Dict[str, Any]]
    validation: ValidationOut
    confidence: float
    svm: Dict[str, SvmResultOut] = Field(default_factory=dict)
    governance: GovernanceOut | None = None


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
    governance: GovernanceOut | None = None


class ExplanationOut(BaseModel):
    type: str
    explanation: str
    confidence: float
    details: Dict[str, Any] = Field(default_factory=dict)


class DecisionTraceStepOut(BaseModel):
    stage: str
    status: str
    timestamp: str | None = None


class DecisionTraceOut(BaseModel):
    trace_id: str
    steps: List[DecisionTraceStepOut] = Field(default_factory=list)


class ProcessExplainOut(BaseModel):
    decision: str
    confidence: float
    explanations: List[ExplanationOut] = Field(default_factory=list)
    trace: DecisionTraceOut
    audit_id: str


class ExplainabilityAuditOut(BaseModel):
    audit_id: str
    record_id: str
    trace_id: str
    decision: str
    confidence: float
    raw_input: Dict[str, Any] = Field(default_factory=dict)
    agent_outputs: Dict[str, Any] = Field(default_factory=dict)
    svm_results: Dict[str, Any] = Field(default_factory=dict)
    policy: Dict[str, Any] = Field(default_factory=dict)
    final: Dict[str, Any] = Field(default_factory=dict)
    explanations: List[Dict[str, Any]] = Field(default_factory=list)
    trace: Dict[str, Any] = Field(default_factory=dict)
    confidence_breakdown: Dict[str, Any] = Field(default_factory=dict)
    formatting_version: str = ""
    rules_version: str = ""
    human_summary: str = ""
    created_at: str | None = None


class OneClickStartIn(BaseModel):
    text: str = Field(min_length=1)
    insurer_number: Optional[str] = None
    auto_call_if_needed: bool = True
    override_guardrails: bool = False


class OneClickStartOut(BaseModel):
    run_id: str
    status: str
    step: str


class OneClickStatusOut(BaseModel):
    run_id: str
    status: str
    step: str
    record_id: Optional[str] = None
    claim_id: Optional[str] = None
    denial_event_id: Optional[int] = None
    call_id: Optional[str] = None
    decision: Optional[str] = None
    output: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)
