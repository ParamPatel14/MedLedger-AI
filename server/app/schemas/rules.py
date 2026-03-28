from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RuleOut(BaseModel):
    id: str
    tpa_name: str
    rule_type: str
    category: str
    value: Optional[float] = None
    value_text: str = ""
    unit: str = ""
    conditions: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    source: str = ""
    version: int = 0
    effective_date: Optional[date] = None


class RuleIngestEmailIn(BaseModel):
    tpa_name: str = ""
    text: str


class RuleIngestWebIn(BaseModel):
    tpa_name: str
    url: str


class RuleIngestGmailIn(BaseModel):
    query: str = ""
    label_ids: List[str] = Field(default_factory=list)
    max_results: int = 10


class RuleIngestOut(BaseModel):
    status: str
    candidates: int = 0
    stored: List[Dict[str, Any]] = Field(default_factory=list)


class RuleListOut(BaseModel):
    items: List[RuleOut] = Field(default_factory=list)
    total: int = 0


class RuleHistoryEventOut(BaseModel):
    id: int
    rule_id: str
    from_version: int
    to_version: int
    diff: Dict[str, Any] = Field(default_factory=dict)
    changed_at: datetime


class RuleHistoryOut(BaseModel):
    rule_id: str
    events: List[RuleHistoryEventOut] = Field(default_factory=list)


class RuleSummaryOut(BaseModel):
    total_active: int = 0
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_tpa: Dict[str, int] = Field(default_factory=dict)


class RuleUpdateOut(BaseModel):
    id: int
    rule_id: str
    from_version: int
    to_version: int
    diff: Dict[str, Any] = Field(default_factory=dict)
    changed_at: datetime
    tpa_name: str = ""
    category: str = ""
    rule_type: str = ""


class RuleUpdatesOut(BaseModel):
    items: List[RuleUpdateOut] = Field(default_factory=list)


class RuleConflictGroupOut(BaseModel):
    tpa_name: str
    category: str
    rule_type: str
    reason: str = ""
    rules: List[Dict[str, Any]] = Field(default_factory=list)


class RuleConflictsOut(BaseModel):
    items: List[RuleConflictGroupOut] = Field(default_factory=list)


class ValidateRuleIn(BaseModel):
    tpa: str
    category: str
    value: float
    rule_type: Optional[str] = None


class ValidateRuleOut(BaseModel):
    valid: bool
    reason: str
    escalate: bool = False
    matched_rule: Optional[RuleOut] = None
