from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.layers.rule_intelligence_layer.config import get_rule_normalization_config


@dataclass(frozen=True)
class NormalizedRuleValue:
    value: Optional[float]
    value_text: str
    unit: str


def _clean_numeric_text(s: str) -> str:
    t = str(s or "").strip()
    t = t.replace(",", "")
    return t


def _parse_multiplier(token: str, multipliers: Dict[str, float]) -> float:
    key = str(token or "").strip().lower()
    if not key:
        return 1.0
    v = multipliers.get(key)
    return float(v) if isinstance(v, (int, float)) else 1.0


def parse_amount(text: str) -> Tuple[Optional[float], str]:
    cfg = get_rule_normalization_config()
    money_cfg = (cfg.get("money") or {}) if isinstance(cfg, dict) else {}
    multipliers = money_cfg.get("multipliers") if isinstance(money_cfg.get("multipliers"), dict) else {}

    raw = str(text or "").strip()
    if not raw:
        return None, ""

    raw = re.sub(r"[₹$€]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()

    m = re.search(r"(?i)\b([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?\b", raw)
    if not m:
        return None, raw
    num_txt = _clean_numeric_text(m.group(1) or "")
    mult_txt = str(m.group(2) or "").strip()
    try:
        base = float(num_txt)
    except Exception:
        return None, raw
    mult = _parse_multiplier(mult_txt, multipliers) if mult_txt else 1.0
    value = base * mult
    return value, f"{value:g}"


def normalize_unit(unit: str) -> str:
    cfg = get_rule_normalization_config()
    unit_cfg = (cfg.get("units") or {}) if isinstance(cfg, dict) else {}
    aliases = unit_cfg.get("aliases") if isinstance(unit_cfg.get("aliases"), dict) else {}

    u = str(unit or "").strip()
    if not u:
        return ""
    key = u.lower()
    mapped = aliases.get(key)
    if isinstance(mapped, str) and mapped.strip():
        return mapped.strip()
    return u


def normalize_value(*, value_text: str, unit: str) -> NormalizedRuleValue:
    value, norm_text = parse_amount(value_text)
    norm_unit = normalize_unit(unit)
    return NormalizedRuleValue(value=value, value_text=norm_text or str(value_text or "").strip(), unit=norm_unit)
