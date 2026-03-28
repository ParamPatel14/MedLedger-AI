from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InsuranceRule(Base):
    __tablename__ = "insurance_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    tpa_name: Mapped[str] = mapped_column(String(128), index=True, default="")
    rule_type: Mapped[str] = mapped_column(String(64), index=True, default="")
    category: Mapped[str] = mapped_column(String(128), index=True, default="")
    key_hash: Mapped[str] = mapped_column(String(64), index=True, default="")

    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str] = mapped_column(String(256), default="")
    unit: Mapped[str] = mapped_column(String(64), default="")
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)

    confidence: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    source: Mapped[str] = mapped_column(String(32), index=True, default="")
    source_ref: Mapped[str] = mapped_column(String(256), default="")
    source_excerpt: Mapped[str] = mapped_column(Text, default="")

    version: Mapped[int] = mapped_column(default=1, index=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)


class InsuranceRuleHistory(Base):
    __tablename__ = "insurance_rule_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(36), index=True, default="")

    from_version: Mapped[int] = mapped_column(default=0, index=True)
    to_version: Mapped[int] = mapped_column(default=0, index=True)

    previous: Mapped[dict] = mapped_column(JSON, default=dict)
    current: Mapped[dict] = mapped_column(JSON, default=dict)
    diff: Mapped[dict] = mapped_column(JSON, default=dict)

    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
