from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClaimCreateIn(BaseModel):
    record_id: Optional[str] = None
    status: str = Field(default="pending")
    claim_data: Dict[str, Any] = Field(default_factory=dict)


class ClaimOut(BaseModel):
    id: str
    record_id: Optional[str] = None
    status: str
    claim_data: Dict[str, Any]


class ClaimStatusUpdateIn(BaseModel):
    claim_id: str
    status: str
    tpa_response_text: str = Field(default="")
    rejection_codes: List[str] = Field(default_factory=list)


class DenialAgentRunOut(BaseModel):
    status: str
    denial_reason: Any = None
    root_cause: Any = None
    action_taken: Any = None
    confidence: float = 0.0
    audit: Dict[str, Any] = Field(default_factory=dict)


class ClaimOutcomeIn(BaseModel):
    claim_id: str
    outcome_status: str


class DenialEmailParseIn(BaseModel):
    text: str


class DenialGmailPullIn(BaseModel):
    query: Optional[str] = None
    label_ids: List[str] = Field(default_factory=list)
    max_results: int = 10
    run_agent: bool = False


class VapiOutboundCallIn(BaseModel):
    claim_id: str
    insurer_number: str
    denial_event_id: Optional[int] = None
    assistant_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    variable_values: Dict[str, Any] = Field(default_factory=dict)
