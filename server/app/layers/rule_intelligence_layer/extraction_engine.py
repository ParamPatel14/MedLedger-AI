from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.layers.rule_intelligence_layer.config import get_rule_extraction_config
from app.layers.rule_intelligence_layer.types import RuleSourceDocument


@dataclass(frozen=True)
class RuleCandidate:
    tpa_name: str
    rule_type: str
    category: str
    value_text: str
    unit: str
    conditions: Dict[str, Any]
    extraction_confidence: float
    source: str
    source_ref: str
    source_excerpt: str
    meta: Dict[str, Any]


def _compile_patterns(patterns: Any) -> List[Dict[str, Any]]:
    compiled: List[Dict[str, Any]] = []
    if not isinstance(patterns, list):
        return compiled
    for p in patterns:
        if not isinstance(p, dict):
            continue
        if p.get("enabled") is False:
            continue
        try:
            rx = re.compile(str(p.get("regex") or ""), re.IGNORECASE | re.MULTILINE)
        except Exception:
            continue
        tpa_rx = None
        if str(p.get("tpa_regex") or "").strip():
            try:
                tpa_rx = re.compile(str(p.get("tpa_regex") or ""), re.IGNORECASE)
            except Exception:
                tpa_rx = None
        compiled.append({**p, "_rx": rx, "_tpa_rx": tpa_rx})
    return compiled


def extract_rule_candidates(doc: RuleSourceDocument) -> List[RuleCandidate]:
    cfg = get_rule_extraction_config()
    patterns = _compile_patterns((cfg.get("patterns") or []) if isinstance(cfg, dict) else [])

    tpa = str(doc.tpa_name or "").strip()
    text = str(doc.text or "")
    out: List[RuleCandidate] = []

    for p in patterns:
        tpa_rx = p.get("_tpa_rx")
        if tpa_rx is not None:
            if not tpa or not tpa_rx.search(tpa):
                continue

        rx = p.get("_rx")
        if rx is None:
            continue
        for m in rx.finditer(text):
            raw_val = ""
            if m.groups():
                raw_val = str(m.group(1) or "").strip()
            if not raw_val:
                raw_val = str(m.group(0) or "").strip()
            if not raw_val:
                continue

            start = max(int(m.start()), 0)
            end = min(int(m.end()), len(text))
            excerpt_start = max(start - int(p.get("excerpt_context") or 80), 0)
            excerpt_end = min(end + int(p.get("excerpt_context") or 80), len(text))
            excerpt = text[excerpt_start:excerpt_end].strip()

            out.append(
                RuleCandidate(
                    tpa_name=tpa,
                    rule_type=str(p.get("rule_type") or "").strip(),
                    category=str(p.get("category") or "").strip(),
                    value_text=raw_val,
                    unit=str(p.get("unit") or "").strip(),
                    conditions=p.get("conditions") if isinstance(p.get("conditions"), dict) else {},
                    extraction_confidence=float(p.get("base_confidence") or 0.0),
                    source=str(doc.source or "").strip(),
                    source_ref=str(doc.source_ref or "").strip(),
                    source_excerpt=excerpt,
                    meta={
                        "pattern_id": str(p.get("id") or "").strip(),
                        "pattern_version": str((cfg.get("version") or "") if isinstance(cfg, dict) else ""),
                        "doc_meta": doc.meta or {},
                    },
                )
            )
    return out
