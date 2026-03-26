from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(32), default="upload", index=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    content_type: Mapped[str] = mapped_column(String(128), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    raw_text: Mapped[str] = mapped_column(Text, default="")

    nlp_model: Mapped[str] = mapped_column(String(128), default="")
    nlp_model_version: Mapped[str] = mapped_column(String(128), default="")
    icd_dataset_version: Mapped[str] = mapped_column(String(64), default="")
    icd_embed_model: Mapped[str] = mapped_column(String(128), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    entities = relationship("ClinicalEntity", back_populates="record", cascade="all, delete-orphan")
    codes = relationship("ClinicalCode", back_populates="record", cascade="all, delete-orphan")
