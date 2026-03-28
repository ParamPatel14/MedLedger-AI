from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class ExplanationItem:
    type: str
    explanation: str
    confidence: float
    meta: Dict[str, Any]

