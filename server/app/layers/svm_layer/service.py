from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.layers.svm_layer.claim_extractor import Claim, ClaimExtractionEngine
from app.layers.svm_layer.config import get_svm_config
from app.layers.svm_layer.verifiers import (
    InterAgentConsistencyVerifier,
    ReasonabilityVerifier,
    SourceAlignmentVerifier,
)
from app.models.svm import SvmAuditLog


def _clamp01(x: float) -> float:
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return float(x)


def _worst_status(statuses: List[str]) -> str:
    order = {"pass": 0, "review": 1, "escalated": 2}
    best = "pass"
    best_v = -1
    for s in statuses:
        key = str(s or "").strip().lower()
        v = order.get(key)
        if v is None:
            continue
        if v > best_v:
            best_v = v
            best = key
    return best


def _require_dict(cfg: Dict[str, Any], path: str) -> Dict[str, Any]:
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict):
            raise RuntimeError(f"SVM config missing: {path}")
        cur = cur.get(part)
    if not isinstance(cur, dict):
        raise RuntimeError(f"SVM config missing: {path}")
    return cur


@dataclass(frozen=True)
class SvmDecision:
    status: str
    trigger_circuit_breaker: bool
    message: str

    def to_dict(self) -> dict:
        return {"status": self.status, "trigger_circuit_breaker": self.trigger_circuit_breaker, "message": self.message}


class SvmMiddleware:
    def __init__(self) -> None:
        self._cfg = None

    def _load_cfg(self) -> Dict[str, Any]:
        self._cfg = get_svm_config()
        return self._cfg

    def _confidence_and_decision(self, cfg: Dict[str, Any], *, scores: Dict[str, float], prior_svm: List[dict]) -> Tuple[float, SvmDecision]:
        scoring = _require_dict(cfg, "scoring")
        weights = scoring.get("weights") or {}
        if not isinstance(weights, dict):
            raise RuntimeError("SVM config missing: scoring.weights")

        w_src = float(weights.get("source_alignment"))
        w_con = float(weights.get("consistency"))
        w_rea = float(weights.get("reasonability"))
        denom = w_src + w_con + w_rea
        if denom <= 0:
            raise RuntimeError("SVM config invalid: scoring.weights must sum to > 0")

        base = (scores.get("source_alignment", 0.0) * w_src + scores.get("consistency", 0.0) * w_con + scores.get("reasonability", 0.0) * w_rea) / denom
        base = _clamp01(base)

        cascade = cfg.get("cascade") or {}
        if not isinstance(cascade, dict):
            cascade = {}
        try:
            warning_penalty = float(cascade.get("warning_penalty"))
        except Exception:
            warning_penalty = 0.0
        try:
            max_penalty = float(cascade.get("max_penalty"))
        except Exception:
            max_penalty = 0.0

        prior_statuses = [str((x or {}).get("status") or "") for x in (prior_svm or []) if isinstance(x, dict)]
        warn_count = sum(1 for s in prior_statuses if str(s).strip().lower() == "review")
        penalty = min(max_penalty, warning_penalty * warn_count) if warning_penalty > 0 else 0.0
        confidence = _clamp01(base - penalty)

        decision_cfg = _require_dict(cfg, "decision")
        try:
            pass_thr = float(decision_cfg.get("pass_threshold"))
            review_thr = float(decision_cfg.get("review_threshold"))
        except Exception as e:
            raise RuntimeError(f"SVM config invalid decision thresholds: {e}") from e

        if confidence > pass_thr:
            return confidence, SvmDecision(status="pass", trigger_circuit_breaker=False, message=str(decision_cfg.get("pass_message") or "Passed SVM verification"))
        if review_thr <= confidence <= pass_thr:
            return confidence, SvmDecision(status="review", trigger_circuit_breaker=False, message=str(decision_cfg.get("review_message") or "SVM warnings; review recommended"))

        cb = cfg.get("circuit_breaker") or {}
        enabled = bool((cb.get("enabled") if isinstance(cb, dict) else True))
        stop = bool((cb.get("stop_on_escalated") if isinstance(cb, dict) else True))
        msg = str(decision_cfg.get("escalated_message") or "Insufficient confidence. Escalating for review.")
        return confidence, SvmDecision(status="escalated", trigger_circuit_breaker=bool(enabled and stop), message=msg)

    def validate(
        self,
        db: Session,
        *,
        record_id: str,
        stage: str,
        agent_name: str,
        raw_text: str,
        agent_input: Dict[str, Any],
        agent_output: Dict[str, Any],
        prior_agent_outputs: List[Dict[str, Any]],
        prior_svm_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        cfg = self._load_cfg()

        extractor = ClaimExtractionEngine(cfg)
        claims, extraction_issues = extractor.extract(agent_name=agent_name, agent_output=agent_output)
        claim_dicts = [c.to_dict() for c in claims]

        source = SourceAlignmentVerifier(cfg)
        consistency = InterAgentConsistencyVerifier(cfg)
        reasonability = ReasonabilityVerifier(cfg)

        v1 = source.verify(raw_text=raw_text, claims=claims)
        prior_claims: List[Claim] = []
        for prev in (prior_agent_outputs or []):
            if not isinstance(prev, dict):
                continue
            an = str(prev.get("agent_name") or "").strip()
            out = prev.get("output") or {}
            if not an or not isinstance(out, dict):
                continue
            cs, _ = extractor.extract(agent_name=an, agent_output=out)
            prior_claims.extend(cs)
        v2 = consistency.verify(current_claims=claims, prior_claims=prior_claims)
        v3 = reasonability.verify(agent_output=agent_output)

        scores = {
            "source_alignment": float(v1.score),
            "consistency": float(v2.score),
            "reasonability": float(v3.score),
        }

        issues: List[dict] = []
        issues.extend(extraction_issues)
        issues.extend(v1.issues)
        issues.extend(v2.issues)
        issues.extend(v3.issues)

        explanations: List[str] = []
        explanations.extend(v1.explanations)
        explanations.extend(v2.explanations)
        explanations.extend(v3.explanations)

        confidence, decision = self._confidence_and_decision(cfg, scores=scores, prior_svm=prior_svm_results)

        out = {
            "status": decision.status,
            "confidence": confidence,
            "issues": issues,
            "claims": claim_dicts,
            "explanations": explanations,
            "scores": scores,
            "decision": decision.to_dict(),
        }

        db.add(
            SvmAuditLog(
                record_id=record_id,
                stage=str(stage),
                agent_name=str(agent_name),
                agent_input=agent_input or {},
                agent_output=agent_output or {},
                claims=claim_dicts,
                scores=scores,
                status=str(decision.status),
                confidence=float(confidence),
                decision=decision.to_dict(),
                issues=issues,
                explanations=explanations,
            )
        )
        db.commit()

        return out

    @staticmethod
    def overall_status(svm_results: Dict[str, Any]) -> str:
        statuses: List[str] = []
        if isinstance(svm_results, dict):
            for v in svm_results.values():
                if isinstance(v, dict):
                    statuses.append(str(v.get("status") or ""))
        return _worst_status(statuses) if statuses else "pass"
