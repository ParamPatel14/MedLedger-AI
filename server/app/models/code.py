from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClinicalCode(Base):
    __tablename__ = "clinical_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinical_records.id", ondelete="CASCADE"), index=True)

    system: Mapped[str] = mapped_column(String(32), default="ICD10", index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    description: Mapped[str] = mapped_column(String(512), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_text: Mapped[str] = mapped_column(String(512), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    record = relationship("ClinicalRecord", back_populates="codes")
