from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RuleSourceDocument:
    source: str
    tpa_name: str
    text: str
    source_ref: str = ""
    received_at: Optional[datetime] = None
    meta: Dict[str, Any] | None = None
