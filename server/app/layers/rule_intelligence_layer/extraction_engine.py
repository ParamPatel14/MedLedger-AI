from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

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


def _candidate_excerpt(*, text: str, start: int, end: int, context: int) -> str:
    s = max(int(start), 0)
    e = min(int(end), len(text))
    excerpt_start = max(s - int(context or 80), 0)
    excerpt_end = min(e + int(context or 80), len(text))
    return text[excerpt_start:excerpt_end].strip()


@lru_cache(maxsize=1)
def _sentencizer():
    import spacy

    nlp = spacy.blank("en")
    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")
    return nlp


def _compile_semantic(cfg: Dict[str, Any]) -> Dict[str, Any]:
    sem = cfg.get("semantic") if isinstance(cfg.get("semantic"), dict) else {}
    enabled = bool(sem.get("enabled"))
    amount_rx = None
    if str(sem.get("amount_regex") or "").strip():
        try:
            amount_rx = re.compile(str(sem.get("amount_regex") or ""), re.IGNORECASE | re.MULTILINE)
        except Exception:
            amount_rx = None

    categories = sem.get("categories") if isinstance(sem.get("categories"), list) else []
    cat_defs: List[Dict[str, Any]] = []
    for c in categories:
        if not isinstance(c, dict) or c.get("enabled") is False:
            continue
        kw = [str(x).strip().lower() for x in (c.get("keywords") or []) if str(x).strip()]
        if not kw:
            continue
        cat_defs.append({**c, "_keywords": kw})

    rule_types = sem.get("rule_types") if isinstance(sem.get("rule_types"), list) else []
    rt_defs: List[Dict[str, Any]] = []
    for r in rule_types:
        if not isinstance(r, dict) or r.get("enabled") is False:
            continue
        kw = [str(x).strip().lower() for x in (r.get("keywords") or []) if str(x).strip()]
        if not kw:
            continue
        rt_defs.append({**r, "_keywords": kw})

    return {"enabled": enabled, "amount_rx": amount_rx, "categories": cat_defs, "rule_types": rt_defs, "raw": sem}


def _choose_rule_type(sentence_lc: str, defs: List[Dict[str, Any]]) -> Tuple[str, float, Dict[str, Any]]:
    best_type = ""
    best_hits = 0
    best_bonus = 0.0
    best_id = ""
    for d in defs:
        kws = d.get("_keywords") or []
        hits = sum(1 for k in kws if k and k in sentence_lc)
        if hits > best_hits:
            best_hits = hits
            best_type = str(d.get("rule_type") or "").strip()
            best_bonus = float(d.get("confidence_bonus") or 0.0)
            best_id = str(d.get("id") or "").strip()
    return best_type, best_bonus, {"rule_type_id": best_id, "keyword_hits": best_hits}


def _semantic_candidates(doc: RuleSourceDocument, cfg: Dict[str, Any]) -> List[RuleCandidate]:
    compiled = _compile_semantic(cfg)
    if not bool(compiled.get("enabled")):
        return []
    amount_rx = compiled.get("amount_rx")
    if amount_rx is None:
        return []

    tpa = str(doc.tpa_name or "").strip()
    text = str(doc.text or "")
    if not text.strip():
        return []

    nlp = _sentencizer()
    parsed = nlp(text)
    sem_raw = compiled.get("raw") if isinstance(compiled.get("raw"), dict) else {}
    min_kw_hits = int(sem_raw.get("min_keyword_hits") or 1)
    excerpt_context = int(sem_raw.get("excerpt_context") or 120)
    base_conf = float(sem_raw.get("base_confidence") or 0.5)
    per_kw_bonus = float(sem_raw.get("per_keyword_bonus") or 0.05)
    max_bonus = float(sem_raw.get("max_keyword_bonus") or 0.2)

    out: List[RuleCandidate] = []
    for sent in parsed.sents:
        s_txt = str(sent.text or "").strip()
        if not s_txt:
            continue
        s_lc = s_txt.lower()

        chosen_type, rt_bonus, rt_meta = _choose_rule_type(s_lc, compiled.get("rule_types") or [])
        for cat in compiled.get("categories") or []:
            kws = cat.get("_keywords") or []
            hits = sum(1 for k in kws if k and k in s_lc)
            if hits < min_kw_hits:
                continue
            m = amount_rx.search(s_txt)
            if not m:
                continue

            raw_val = ""
            if m.groups():
                raw_val = str(m.group(m.lastindex or 1) or "").strip()
            if not raw_val:
                raw_val = str(m.group(0) or "").strip()
            if not raw_val:
                continue

            conf = base_conf + min(float(hits) * per_kw_bonus, max_bonus) + float(cat.get("confidence_bonus") or 0.0) + float(rt_bonus or 0.0)
            excerpt = _candidate_excerpt(text=text, start=int(sent.start_char), end=int(sent.end_char), context=excerpt_context)

            out.append(
                RuleCandidate(
                    tpa_name=tpa,
                    rule_type=str((chosen_type or cat.get("rule_type") or "")).strip(),
                    category=str(cat.get("category") or "").strip(),
                    value_text=raw_val,
                    unit=str(cat.get("unit") or "").strip(),
                    conditions=cat.get("conditions") if isinstance(cat.get("conditions"), dict) else {},
                    extraction_confidence=float(conf),
                    source=str(doc.source or "").strip(),
                    source_ref=str(doc.source_ref or "").strip(),
                    source_excerpt=excerpt,
                    meta={
                        "match_type": "semantic",
                        "match_strength": float(hits),
                        "semantic_category_id": str(cat.get("id") or "").strip(),
                        "semantic_keyword_hits": int(hits),
                        "semantic_rule_type": str(chosen_type or ""),
                        "semantic_rule_type_meta": rt_meta,
                        "pattern_version": str((cfg.get("version") or "") if isinstance(cfg, dict) else ""),
                        "doc_meta": doc.meta or {},
                    },
                )
            )
    return out


def _regex_candidates(doc: RuleSourceDocument, cfg: Dict[str, Any]) -> List[RuleCandidate]:
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

            excerpt = _candidate_excerpt(text=text, start=int(m.start()), end=int(m.end()), context=int(p.get("excerpt_context") or 80))
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
                        "match_type": "regex",
                        "match_strength": 1.0,
                        "pattern_id": str(p.get("id") or "").strip(),
                        "pattern_version": str((cfg.get("version") or "") if isinstance(cfg, dict) else ""),
                        "doc_meta": doc.meta or {},
                    },
                )
            )
    return out


def extract_rule_candidates(doc: RuleSourceDocument) -> List[RuleCandidate]:
    cfg = get_rule_extraction_config()
    regex = _regex_candidates(doc, cfg if isinstance(cfg, dict) else {})
    semantic = _semantic_candidates(doc, cfg if isinstance(cfg, dict) else {})
    return regex + semantic
