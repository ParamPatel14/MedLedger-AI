from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from sqlalchemy.orm import Session

from app.layers.rule_intelligence_layer.confidence import score_confidence
from app.layers.rule_intelligence_layer.extraction_engine import RuleCandidate, extract_rule_candidates
from app.layers.rule_intelligence_layer.normalization import NormalizedRuleValue, normalize_value
from app.layers.rule_intelligence_layer.storage import RuleStorageService
from app.layers.rule_intelligence_layer.types import RuleSourceDocument


class RuleGraphState(TypedDict, total=False):
    source_docs: List[RuleSourceDocument]
    candidates: List[RuleCandidate]
    normalized: List[Dict[str, Any]]
    stored: List[Dict[str, Any]]
    audit: Dict[str, Any]


class RuleLangGraphPipeline:
    def __init__(self) -> None:
        self._storage = RuleStorageService()

    def run(self, db: Session, *, docs: List[RuleSourceDocument]) -> Dict[str, Any]:
        from langgraph.graph import END, StateGraph

        def load_node(state: RuleGraphState) -> RuleGraphState:
            state["source_docs"] = docs
            state["candidates"] = []
            state["normalized"] = []
            state["stored"] = []
            state["audit"] = {}
            return state

        def extract_node(state: RuleGraphState) -> RuleGraphState:
            out: List[RuleCandidate] = []
            for d in state.get("source_docs") or []:
                out.extend(extract_rule_candidates(d))
            state["candidates"] = out
            return state

        def normalize_node(state: RuleGraphState) -> RuleGraphState:
            rows: List[Dict[str, Any]] = []
            for c in state.get("candidates") or []:
                norm = normalize_value(value_text=c.value_text, unit=c.unit)
                rows.append({"candidate": c, "normalized": norm})
            state["normalized"] = rows
            return state

        def score_node(state: RuleGraphState) -> RuleGraphState:
            rows: List[Dict[str, Any]] = []
            for item in state.get("normalized") or []:
                cand = item.get("candidate")
                norm = item.get("normalized")
                if not isinstance(cand, RuleCandidate) or not isinstance(norm, NormalizedRuleValue):
                    continue
                meta = cand.meta if isinstance(getattr(cand, "meta", None), dict) else {}
                decision = score_confidence(
                    extraction_confidence=float(cand.extraction_confidence or 0.0),
                    source=str(cand.source or ""),
                    match_type=str(meta.get("match_type") or ""),
                    match_strength=float(meta.get("match_strength") or 1.0),
                )
                rows.append({**item, "confidence": decision.confidence, "decision": decision})
            state["normalized"] = rows
            return state

        def store_node(state: RuleGraphState) -> RuleGraphState:
            stored: List[Dict[str, Any]] = []
            for item in state.get("normalized") or []:
                cand = item.get("candidate")
                norm = item.get("normalized")
                decision = item.get("decision")
                if not isinstance(cand, RuleCandidate) or not isinstance(norm, NormalizedRuleValue) or decision is None:
                    continue
                if not bool(getattr(decision, "usable", False)):
                    stored.append(
                        {
                            "stored": False,
                            "reason": "low_confidence",
                            "confidence": float(getattr(decision, "confidence", 0.0)),
                            "candidate": {"tpa_name": cand.tpa_name, "rule_type": cand.rule_type, "category": cand.category},
                            "audit": getattr(decision, "audit", {}) if isinstance(getattr(decision, "audit", None), dict) else {},
                        }
                    )
                    continue
                row, changed = self._storage.upsert(
                    db,
                    candidate=cand,
                    normalized=norm,
                    confidence=float(getattr(decision, "confidence", 0.0)),
                    effective_date=None,
                    extra_meta={"confidence_audit": getattr(decision, "audit", {})},
                )
                stored.append(
                    {
                        "stored": True,
                        "changed": bool(changed),
                        "rule_id": row.id,
                        "version": int(row.version or 0),
                        "confidence": float(row.confidence or 0.0),
                        "key": {"tpa_name": row.tpa_name, "rule_type": row.rule_type, "category": row.category},
                    }
                )
            state["stored"] = stored
            return state

        g = StateGraph(RuleGraphState)
        g.add_node("load", load_node)
        g.add_node("extract", extract_node)
        g.add_node("normalize", normalize_node)
        g.add_node("score", score_node)
        g.add_node("store", store_node)

        g.set_entry_point("load")
        g.add_edge("load", "extract")
        g.add_edge("extract", "normalize")
        g.add_edge("normalize", "score")
        g.add_edge("score", "store")
        g.add_edge("store", END)

        out_state = g.compile().invoke({})
        return {
            "status": "ok",
            "candidates": len(out_state.get("candidates") or []),
            "stored": out_state.get("stored") or [],
        }
