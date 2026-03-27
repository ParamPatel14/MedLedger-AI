from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SvmAuditLog(Base):
    __tablename__ = "svm_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[str] = mapped_column(String(36), ForeignKey("records.id", ondelete="CASCADE"), index=True)

    stage: Mapped[str] = mapped_column(String(96), index=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)

    agent_input: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_output: Mapped[dict] = mapped_column(JSON, default=dict)

    claims: Mapped[list] = mapped_column(JSON, default=list)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(16), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    decision: Mapped[dict] = mapped_column(JSON, default=dict)

    issues: Mapped[list] = mapped_column(JSON, default=list)
    explanations: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

