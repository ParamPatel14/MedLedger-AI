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


def score_confidence(*, extraction_confidence: float, source: str, match_type: str = "", match_strength: float = 1.0) -> ConfidenceDecision:
    cfg = get_rule_confidence_config()
    weights = cfg.get("source_weights") if isinstance(cfg, dict) and isinstance(cfg.get("source_weights"), dict) else {}
    w = float(weights.get(str(source or "").strip(), cfg.get("default_source_weight") or 0.5) or 0.0)

    mt_weights = cfg.get("match_type_weights") if isinstance(cfg, dict) and isinstance(cfg.get("match_type_weights"), dict) else {}
    mt = str(match_type or "").strip().lower()
    mt_w = float(mt_weights.get(mt, cfg.get("default_match_type_weight") or 1.0) or 0.0)

    ms = float(match_strength or 0.0)
    if ms < 0.0:
        ms = 0.0
    ms_cap = float(cfg.get("max_match_strength") or 1.0) if isinstance(cfg, dict) else 1.0
    if ms_cap > 0:
        ms = min(ms, ms_cap)
    ms_norm = ms / ms_cap if ms_cap > 0 else 1.0

    conf = _clamp(float(extraction_confidence or 0.0) * _clamp(w) * _clamp(mt_w) * _clamp(ms_norm if ms_norm else 1.0))

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
            "match_type": mt,
            "match_type_weight": mt_w,
            "match_strength": float(match_strength or 0.0),
            "match_strength_norm": float(ms_norm or 0.0),
            "extraction_confidence": float(extraction_confidence or 0.0),
            "min_store_confidence": min_store,
            "min_use_confidence": min_use,
        },
    )
