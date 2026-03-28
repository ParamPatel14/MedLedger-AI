from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from app.layers.rule_intelligence_layer.config import get_rule_confidence_config


def _clamp(x: float) -> float:
    v = float(x or 0.0)
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


@dataclass(frozen=True)
class ConfidenceDecision:
    confidence: float
    usable: bool
    use_for_validation: bool
    audit: Dict[str, Any]


def score_confidence(*, extraction_confidence: float, source: str) -> ConfidenceDecision:
    cfg = get_rule_confidence_config()
    weights = cfg.get("source_weights") if isinstance(cfg, dict) and isinstance(cfg.get("source_weights"), dict) else {}
    w = float(weights.get(str(source or "").strip(), cfg.get("default_source_weight") or 0.5) or 0.0)
    conf = _clamp(float(extraction_confidence or 0.0) * _clamp(w))

    min_store = float(cfg.get("min_store_confidence") or 0.0) if isinstance(cfg, dict) else 0.0
    min_use = float(cfg.get("min_use_confidence") or 1.0) if isinstance(cfg, dict) else 1.0

    usable = conf >= float(min_store)
    use_for_validation = conf >= float(min_use)
    return ConfidenceDecision(
        confidence=conf,
        usable=usable,
        use_for_validation=use_for_validation,
        audit={
            "rule_confidence_version": str((cfg.get("version") or "") if isinstance(cfg, dict) else ""),
            "source_weight": w,
            "extraction_confidence": float(extraction_confidence or 0.0),
            "min_store_confidence": min_store,
            "min_use_confidence": min_use,
        },
    )
