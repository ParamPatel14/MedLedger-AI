from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClinicalEntity(Base):
    __tablename__ = "clinical_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinical_records.id", ondelete="CASCADE"), index=True)

    type: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[str] = mapped_column(String(512), default="")
    normalized_value: Mapped[str] = mapped_column(String(512), default="")
    ontology_id: Mapped[str] = mapped_column(String(128), default="")

    start: Mapped[int] = mapped_column(Integer, default=0)
    end: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    record = relationship("ClinicalRecord", back_populates="entities")
