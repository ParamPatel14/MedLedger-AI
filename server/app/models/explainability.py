from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExplainabilityAuditTrail(Base):
    __tablename__ = "explainability_audit_trails"

    id: Mapped[int] = mapped_column(primary_key=True)
    audit_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    record_id: Mapped[str] = mapped_column(String(36), ForeignKey("records.id", ondelete="CASCADE"), index=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True, default="")

    decision: Mapped[str] = mapped_column(String(16), index=True, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0, index=True)

    raw_input: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    svm_results: Mapped[dict] = mapped_column(JSON, default=dict)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)
    final: Mapped[dict] = mapped_column(JSON, default=dict)

    explanations: Mapped[list] = mapped_column(JSON, default=list)
    trace: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    formatting_version: Mapped[str] = mapped_column(String(32), default="")
    rules_version: Mapped[str] = mapped_column(String(32), default="")

    human_summary: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

