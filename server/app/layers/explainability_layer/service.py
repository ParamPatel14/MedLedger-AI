from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.layers.explainability_layer.explanation_engine import DecisionExplanationEngine
from app.layers.explainability_layer.trace_engine import DecisionTraceEngine
from app.layers.svm_layer.service import SvmMiddleware
from app.layers.governance_layer.config import get_governance_thresholds
from app.models.explainability import ExplainabilityAuditTrail


def _as_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _clamp01(x: float) -> float:
    v = float(x or 0.0)
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _min_score(items: List[float]) -> float:
    vals = [float(x) for x in items if isinstance(x, (int, float))]
    return min(vals) if vals else 0.0


class ExplainabilityService:
    def __init__(self) -> None:
        self._engine = DecisionExplanationEngine()
        self._trace = DecisionTraceEngine()

    def _confidence_breakdown(self, *, ctx: Dict[str, Any]) -> Dict[str, Any]:
        thr = get_governance_thresholds()
        thr_vals = thr.get("thresholds") if isinstance(thr, dict) and isinstance(thr.get("thresholds"), dict) else {}
        c_cfg = thr.get("confidence") if isinstance(thr, dict) and isinstance(thr.get("confidence"), dict) else {}

        clinical_conf = _clamp01(_as_float(_as_dict(ctx.get("clinical")).get("confidence")))
        coding_conf = _clamp01(_as_float(_as_dict(ctx.get("coding")).get("confidence")))
        rule_conf = _clamp01(_as_float(_as_dict(ctx.get("validation")).get("confidence")))

        svm = _as_dict(ctx.get("svm"))
        stages = c_cfg.get("svm_stages") if isinstance(c_cfg.get("svm_stages"), list) else []
        svm_values: List[float] = []
        for st in stages:
            key = str(st or "").strip()
            v = svm.get(key)
            if isinstance(v, dict):
                svm_values.append(_clamp01(_as_float(v.get("confidence"))))
        svm_conf = min(svm_values) if svm_values else 0.0

        final_conf = _clamp01(_as_float(_as_dict(ctx.get("governance")).get("confidence") or ctx.get("workflow_confidence")))

        return {
            "clinical_confidence": clinical_conf,
            "coding_confidence": coding_conf,
            "svm_confidence": svm_conf,
            "rule_confidence": rule_conf,
            "final_confidence": final_conf,
            "thresholds": {k: _as_float(v) for k, v in thr_vals.items()},
            "confidence_config": c_cfg,
            "thresholds_version": str((thr.get("version") or "") if isinstance(thr, dict) else ""),
        }

    def build_and_store(
        self,
        db: Session,
        *,
        record_id: str,
        raw_text: str,
        clinical: Dict[str, Any],
        coding: Dict[str, Any],
        validation: Dict[str, Any],
        svm: Dict[str, Any],
        governance: Dict[str, Any],
        workflow_confidence: float,
    ) -> Dict[str, Any]:
        svm_stages: List[Dict[str, Any]] = []
        if isinstance(svm, dict):
            for stage, payload in svm.items():
                if not isinstance(payload, dict):
                    continue
                svm_stages.append(
                    {
                        "stage": str(stage),
                        "status": str(payload.get("status") or ""),
                        "confidence": _clamp01(_as_float(payload.get("confidence") or 0.0)),
                        "scores": payload.get("scores") if isinstance(payload.get("scores"), dict) else {},
                    }
                )

        score_src: List[float] = []
        score_cons: List[float] = []
        score_reason: List[float] = []
        stage_conf: List[float] = []
        for st in svm_stages:
            scores = st.get("scores") if isinstance(st.get("scores"), dict) else {}
            score_src.append(_as_float(scores.get("source_alignment")))
            score_cons.append(_as_float(scores.get("consistency")))
            score_reason.append(_as_float(scores.get("reasonability")))
            stage_conf.append(_as_float(st.get("confidence")))

        svm_overall_status = str(SvmMiddleware.overall_status(svm if isinstance(svm, dict) else {}))
        svm_overall = {
            "status": svm_overall_status,
            "confidence": _clamp01(_min_score(stage_conf)),
            "details": {
                "source_alignment": _clamp01(_min_score(score_src)),
                "consistency": _clamp01(_min_score(score_cons)),
                "reasonability": _clamp01(_min_score(score_reason)),
            },
        }

        ctx: Dict[str, Any] = {
            "record_id": str(record_id),
            "raw_text": str(raw_text or ""),
            "clinical": clinical or {},
            "coding": coding or {},
            "validation": validation or {},
            "svm": svm or {},
            "svm_stages": svm_stages,
            "svm_overall": svm_overall,
            "governance": governance or {},
            "workflow_confidence": float(workflow_confidence or 0.0),
            "thresholds": get_governance_thresholds(),
        }

        explanations = self._engine.explain(ctx=ctx)
        trace = self._trace.build_trace(db, record_id=str(record_id))
        breakdown = self._confidence_breakdown(ctx=ctx)

        decision = str((_as_dict(governance).get("decision") or "APPROVE")).strip().upper() or "APPROVE"
        conf = _clamp01(_as_float(_as_dict(governance).get("confidence") or workflow_confidence))

        svm_verification_item = next((e for e in explanations if e.type == "svm_verification" and str(e.explanation or "").strip()), None)
        svm_verification = {
            "status": str(svm_overall_status),
            "explanation": str(svm_verification_item.explanation) if svm_verification_item else "",
            "details": dict(svm_overall.get("details") or {}),
        }

        row = ExplainabilityAuditTrail(
            record_id=str(record_id),
            trace_id=str(trace.get("trace_id") or str(record_id)),
            decision=decision,
            confidence=float(conf),
            raw_input={"text": str(raw_text or "")},
            agent_outputs={"clinical": clinical or {}, "coding": coding or {}, "validation": validation or {}},
            svm_results=svm or {},
            policy={"issues": list((_as_dict(governance).get("issues") or [])), "reason": str((_as_dict(governance).get("reason") or ""))},
            final={"decision": decision, "confidence": float(conf), "audit_id": str((_as_dict(governance).get("audit_id") or ""))},
            explanations=[{"type": e.type, "explanation": e.explanation, "confidence": e.confidence, "meta": e.meta} for e in explanations],
            trace=trace,
            confidence_breakdown=breakdown,
            formatting_version=self._engine.templates_version,
            rules_version=self._engine.rules_version,
            human_summary="\n".join([e.explanation for e in explanations if str(e.explanation or "").strip()]),
            meta={"governance_audit_id": str((_as_dict(governance).get("audit_id") or "")), "svm_overall": svm_overall},
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        return {
            "decision": decision,
            "confidence": float(conf),
            "explanations": [
                {"type": e.type, "explanation": e.explanation, "confidence": float(e.confidence)}
                for e in explanations
                if str(e.explanation or "").strip() and e.type != "svm_verification"
            ],
            "svm_verification": svm_verification,
            "confidence_transparency": breakdown,
            "trace": trace,
            "audit_id": str(row.audit_id),
        }
