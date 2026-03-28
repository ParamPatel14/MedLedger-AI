from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)

    record_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("records.id", ondelete="SET NULL"), index=True, nullable=True)
    claim_data: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)


class DenialEvent(Base):
    __tablename__ = "denial_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), index=True)

    status: Mapped[str] = mapped_column(String(32), index=True)
    raw_reason_text: Mapped[str] = mapped_column(Text, default="")
    rejection_codes: Mapped[list] = mapped_column(JSON, default=list)

    structured_reasons: Mapped[list] = mapped_column(JSON, default=list)
    source_meta: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CorrectionApplied(Base):
    __tablename__ = "corrections_applied"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    denial_event_id: Mapped[int] = mapped_column(ForeignKey("denial_events.id", ondelete="SET NULL"), nullable=True, index=True)

    strategy_id: Mapped[str] = mapped_column(String(96), index=True, default="")
    actions: Mapped[list] = mapped_column(JSON, default=list)
    patch: Mapped[list] = mapped_column(JSON, default=list)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Resubmission(Base):
    __tablename__ = "resubmissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    correction_id: Mapped[int] = mapped_column(ForeignKey("corrections_applied.id", ondelete="SET NULL"), nullable=True, index=True)

    resubmitted_claim: Mapped[dict] = mapped_column(JSON, default=dict)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)

    outcome: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class LearningLog(Base):
    __tablename__ = "learning_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), index=True)

    denial_type: Mapped[str] = mapped_column(String(64), index=True, default="")
    root_cause_category: Mapped[str] = mapped_column(String(64), index=True, default="")
    strategy_id: Mapped[str] = mapped_column(String(96), index=True, default="")
    outcome: Mapped[str] = mapped_column(String(32), index=True, default="")

    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
