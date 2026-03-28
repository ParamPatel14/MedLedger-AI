from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.layers.denial_layer.config import get_denial_mappings, get_denial_rules, get_denial_thresholds
from app.layers.denial_layer.correction_engine import CorrectionEngine
from app.layers.denial_layer.learning import LearningService
from app.layers.denial_layer.reason_engine import DenialReasonEngine
from app.layers.denial_layer.resubmission_engine import ResubmissionEngine
from app.layers.denial_layer.root_cause_engine import RootCauseEngine
from app.layers.denial_layer.utils import JsonPatchOp, detect_patch_conflicts
from app.layers.governance_layer.evaluation import DecisionInputs, evaluate_condition
from app.models.denial import Claim, CorrectionApplied, DenialEvent, Resubmission


logger = logging.getLogger(__name__)


class DenialGraphState(TypedDict, total=False):
    claim_id: str
    claim_record_id: Optional[str]
    claim_status: str
    claim_data: dict
    denial_event_id: int
    denial_status: str
    denial_raw_reason: str
    rejection_codes: list

    denial_reasons: list
    root_cause: dict
    correction: dict
    escalated: bool
    escalation: dict
    resubmission: dict

    issues: list
    confidence: float
    audit: dict


class DenialManagementAgent:
    def __init__(self) -> None:
        self._reason_engine = DenialReasonEngine()
        self._root_cause = RootCauseEngine()
        self._correction = CorrectionEngine()
        self._resubmission = ResubmissionEngine()
        self._learning = LearningService()

    def run_for_denial_event(self, db: Session, *, claim_id: str, denial_event_id: int) -> Dict[str, Any]:
        from langgraph.graph import END, StateGraph

        mappings_cfg = get_denial_mappings()
        thresholds_cfg = get_denial_thresholds()
        rules_cfg = get_denial_rules()

        def load_node(state: DenialGraphState) -> DenialGraphState:
            claim = db.query(Claim).filter(Claim.id == claim_id).first()
            if claim is None:
                raise ValueError("Claim not found")
            ev = db.query(DenialEvent).filter(DenialEvent.id == int(denial_event_id)).first()
            if ev is None:
                raise ValueError("Denial event not found")
            state["claim_id"] = claim.id
            state["claim_record_id"] = claim.record_id
            state["claim_status"] = claim.status
            state["claim_data"] = claim.claim_data or {}
            state["denial_event_id"] = ev.id
            state["denial_status"] = ev.status
            state["denial_raw_reason"] = ev.raw_reason_text or ""
            state["rejection_codes"] = ev.rejection_codes or []
            state["issues"] = []
            state["audit"] = {
                "denial_mappings_version": str(mappings_cfg.get("version") or ""),
                "denial_rules_version": str(rules_cfg.get("version") or ""),
                "denial_thresholds_version": str(thresholds_cfg.get("version") or ""),
            }
            return state

        def should_activate(state: DenialGraphState) -> str:
            trig = (thresholds_cfg.get("triggers") or {}) if isinstance(thresholds_cfg.get("triggers"), dict) else {}
            allowed = {str(x).strip().lower() for x in (trig.get("activate_on_status") or []) if str(x).strip()}
            status = str(state.get("denial_status") or "").strip().lower()
            return "activate" if (not allowed or status in allowed) else "ignore"

        def reason_node(state: DenialGraphState) -> DenialGraphState:
            reasons = self._reason_engine.extract(
                mappings_cfg=mappings_cfg,
                raw_reason_text=str(state.get("denial_raw_reason") or ""),
                rejection_codes=[str(x or "") for x in (state.get("rejection_codes") or [])],
            )
            state["denial_reasons"] = [r.to_dict() for r in reasons]
            ev = db.query(DenialEvent).filter(DenialEvent.id == int(state.get("denial_event_id"))).first()
            if ev is not None:
                ev.structured_reasons = state["denial_reasons"]
                db.commit()
            return state

        def rca_node(state: DenialGraphState) -> DenialGraphState:
            denial_reasons = state.get("denial_reasons") or []
            types = [str(r.get("type") or "").strip() for r in denial_reasons if isinstance(r, dict)]
            rc = self._root_cause.analyze(
                rules_cfg=rules_cfg,
                thresholds_cfg=thresholds_cfg,
                ctx={"claim": {"claim_data": state.get("claim_data") or {}}, "svm": (state.get("claim_data") or {}).get("svm") or {}},
                denial_reason_types=types,
                workflow_confidence=float(state.get("confidence") or 0.0),
                raw_text=str(state.get("denial_raw_reason") or ""),
            )
            state["root_cause"] = rc.to_dict()
            return state

        def loop_node(state: DenialGraphState) -> DenialGraphState:
            loop_cfg = thresholds_cfg.get("loop_detection") or {}
            max_total = int(loop_cfg.get("max_denials_total", 0) or 0)
            max_same = int(loop_cfg.get("max_denials_same_type", 0) or 0)

            denial_reasons = state.get("denial_reasons") or []
            types = [str(r.get("type") or "").strip() for r in denial_reasons if isinstance(r, dict) and str(r.get("type") or "").strip()]
            main_type = types[0] if types else "unknown"

            total_denials = int(
                db.query(func.count(DenialEvent.id))
                .filter(DenialEvent.claim_id == claim_id)
                .filter(DenialEvent.status.in_(["denied", "query"]))
                .scalar()
                or 0
            )
            same_type_denials = 0
            if main_type:
                rows = (
                    db.query(DenialEvent.structured_reasons)
                    .filter(DenialEvent.claim_id == claim_id)
                    .filter(DenialEvent.status.in_(["denied", "query"]))
                    .all()
                )
                for (sr,) in rows:
                    if not isinstance(sr, list):
                        continue
                    if any(isinstance(x, dict) and str(x.get("type") or "").strip() == main_type for x in sr):
                        same_type_denials += 1

            if (max_total and total_denials > max_total) or (max_same and same_type_denials > max_same):
                issues = state.get("issues") or []
                issues.append({"type": "denial_loop", "severity": "critical", "total_denials": total_denials, "same_type": same_type_denials})
                state["issues"] = issues
            state["audit"]["loop"] = {"total_denials": total_denials, "same_type_denials": same_type_denials, "main_type": main_type}
            return state

        def correction_node(state: DenialGraphState) -> DenialGraphState:
            claim_data = state.get("claim_data") or {}
            denial_reasons = state.get("denial_reasons") or []
            root_cause = state.get("root_cause") or {}
            out = self._correction.apply(
                db,
                rules_cfg=rules_cfg,
                thresholds_cfg=thresholds_cfg,
                ctx={"raw_text": str(state.get("denial_raw_reason") or ""), "confidence": float(state.get("confidence") or 0.0)},
                claim_record_id=state.get("claim_record_id"),
                claim_data=claim_data if isinstance(claim_data, dict) else {},
                denial_reasons=denial_reasons if isinstance(denial_reasons, list) else [],
                root_cause=root_cause if isinstance(root_cause, dict) else {},
                workflow_confidence=float(state.get("confidence") or 0.0),
            )
            state["correction"] = out.to_dict()
            state["claim_data"] = out.updated_claim_data

            issues = state.get("issues") or []
            issues.extend(out.issues)
            state["issues"] = issues

            state["confidence"] = float(out.confidence or 0.0)
            state["audit"]["strategies"] = [s.to_dict() for s in out.selections]
            return state

        def decide_node(state: DenialGraphState) -> DenialGraphState:
            issues = state.get("issues") or []
            correction = state.get("correction") or {}
            patch = correction.get("patch") or []
            conflict_cfg = rules_cfg.get("conflict_policy") or {}
            conflict_fields = conflict_cfg.get("conflict_fields") or []
            if not isinstance(conflict_fields, list):
                conflict_fields = []
            patch_ops: List[JsonPatchOp] = []
            for p in patch:
                if isinstance(p, dict):
                    patch_ops.append(JsonPatchOp(op=str(p.get("op") or ""), path=str(p.get("path") or ""), value=p.get("value")))
            issues.extend(detect_patch_conflicts(patch_ops, [str(x or "") for x in conflict_fields if str(x or "").strip()]))
            state["issues"] = issues

            thr_cfg = (thresholds_cfg.get("thresholds") or {}) if isinstance(thresholds_cfg.get("thresholds"), dict) else {}
            min_conf = float(thr_cfg.get("min_strategy_confidence", 0.0) or 0.0)

            decision_inputs = DecisionInputs(
                raw_text=str(state.get("denial_raw_reason") or ""),
                workflow_confidence=float(state.get("confidence") or 0.0),
                svm={},
                policy_issues=[],
                edge_issues=[],
                external_issues=issues if isinstance(issues, list) else [],
            )
            escalation_cfg = rules_cfg.get("escalation") or {}
            esc_rules = escalation_cfg.get("rules") or []
            if not isinstance(esc_rules, list):
                esc_rules = []

            escalated = False
            matched_rule = None
            for r in esc_rules:
                if not isinstance(r, dict):
                    continue
                cond = r.get("when") or {}
                if not isinstance(cond, dict):
                    continue
                if evaluate_condition(cond, ctx={"thresholds": thresholds_cfg, **state}, decision_inputs=decision_inputs):
                    escalated = True
                    matched_rule = r
                    break

            if float(state.get("confidence") or 0.0) < min_conf:
                escalated = True
                if matched_rule is None:
                    matched_rule = {"id": "low_confidence", "reason": "Low confidence in correction strategy"}

            no_actions = not bool((correction.get("selections") or []))
            if no_actions:
                escalated = True
                if matched_rule is None:
                    matched_rule = {"id": "no_strategy", "reason": "No correction strategy selected"}

            mode = str((conflict_cfg.get("mode") or "escalate")).strip().lower()
            if mode == "escalate" and any(str(x.get("type") or "") == "conflicting_fixes" for x in (issues or []) if isinstance(x, dict)):
                escalated = True
                if matched_rule is None:
                    matched_rule = {"id": "conflicting_fixes", "reason": "Conflicting fixes detected"}

            state["escalated"] = bool(escalated)
            if escalated:
                state["escalation"] = {
                    "status": "escalated",
                    "reason": str((matched_rule or {}).get("reason") or "Escalated"),
                    "matched_rule_id": str((matched_rule or {}).get("id") or ""),
                    "queue": str(escalation_cfg.get("queue") or ""),
                }
            return state

        def resubmit_node(state: DenialGraphState) -> DenialGraphState:
            result = self._resubmission.resubmit(
                db,
                claim_record_id=state.get("claim_record_id"),
                updated_claim_data=state.get("claim_data") or {},
                thresholds_cfg=thresholds_cfg,
                rules_cfg=rules_cfg,
                workflow_confidence=float(state.get("confidence") or 0.0),
            )
            state["resubmission"] = result.to_dict()
            return state

        def route_after_decide(state: DenialGraphState) -> str:
            return "end_escalated" if bool(state.get("escalated")) else "do_resubmit"

        graph = StateGraph(DenialGraphState)
        graph.add_node("load", load_node)
        graph.add_node("reason", reason_node)
        graph.add_node("rca", rca_node)
        graph.add_node("loop", loop_node)
        graph.add_node("correction", correction_node)
        graph.add_node("decide", decide_node)
        graph.add_node("resubmit", resubmit_node)

        graph.set_entry_point("load")
        graph.add_conditional_edges("load", should_activate, {"activate": "reason", "ignore": END})
        graph.add_edge("reason", "rca")
        graph.add_edge("rca", "loop")
        graph.add_edge("loop", "correction")
        graph.add_edge("correction", "decide")
        graph.add_conditional_edges("decide", route_after_decide, {"do_resubmit": "resubmit", "end_escalated": END})
        graph.add_edge("resubmit", END)
        app = graph.compile()

        initial: DenialGraphState = {"confidence": 0.0}
        state = app.invoke(initial)

        if state.get("denial_reasons") is None:
            return {
                "status": "ignored",
                "denial_reason": None,
                "root_cause": None,
                "action_taken": None,
                "confidence": 0.0,
                "audit": state.get("audit") or {},
            }

        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if claim is None:
            raise ValueError("Claim not found")

        correction = state.get("correction") or {}
        correction_row = CorrectionApplied(
            claim_id=claim_id,
            denial_event_id=int(denial_event_id),
            strategy_id=str(((correction.get("selections") or [{}])[0] or {}).get("strategy_id") or ""),
            actions=[s.get("actions") for s in (correction.get("selections") or []) if isinstance(s, dict)],
            patch=correction.get("patch") or [],
            confidence=float(state.get("confidence") or 0.0),
            meta={
                "denial_reasons": state.get("denial_reasons") or [],
                "root_cause": state.get("root_cause") or {},
                "issues": state.get("issues") or [],
                "audit": state.get("audit") or {},
                "selected_strategies": correction.get("selections") or [],
            },
        )
        db.add(correction_row)
        db.commit()
        db.refresh(correction_row)

        if bool(state.get("escalated")):
            return {
                "status": "escalated",
                "denial_reason": state.get("denial_reasons"),
                "root_cause": state.get("root_cause"),
                "action_taken": state.get("escalation"),
                "confidence": float(state.get("confidence") or 0.0),
                "audit": {"correction_id": correction_row.id, **(state.get("audit") or {})},
            }

        claim.claim_data = state.get("claim_data") or {}
        trig = (thresholds_cfg.get("triggers") or {}) if isinstance(thresholds_cfg.get("triggers"), dict) else {}
        claim.status = str(trig.get("resubmission_status") or "resubmitted")
        db.commit()

        res = Resubmission(
            claim_id=claim_id,
            correction_id=correction_row.id,
            resubmitted_claim=claim.claim_data or {},
            validation=state.get("resubmission") or {},
            outcome="pending",
        )
        db.add(res)
        db.commit()
        db.refresh(res)

        return {
            "status": "resubmitted",
            "denial_reason": state.get("denial_reasons"),
            "root_cause": state.get("root_cause"),
            "action_taken": {"correction_id": correction_row.id, "resubmission_id": res.id, "strategies": correction.get("selections") or []},
            "confidence": float(state.get("confidence") or 0.0),
            "audit": {"correction_id": correction_row.id, "resubmission_id": res.id, **(state.get("audit") or {})},
        }

    def record_outcome(self, db: Session, *, claim_id: str, outcome_status: str) -> None:
        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if claim is None:
            return
        claim.status = str(outcome_status or claim.status)
        db.commit()

        res = db.query(Resubmission).filter(Resubmission.claim_id == claim_id).order_by(Resubmission.id.desc()).first()
        if res is not None and str(res.outcome or "").strip().lower() == "pending":
            res.outcome = str(outcome_status or "")
            db.commit()

        corr = db.query(CorrectionApplied).filter(CorrectionApplied.claim_id == claim_id).order_by(CorrectionApplied.id.desc()).first()
        if corr is None or not isinstance(corr.meta, dict):
            return

        denial_reasons = corr.meta.get("denial_reasons") or []
        root = corr.meta.get("root_cause") or {}
        root_cat = str(root.get("category") or "").strip() or "unknown"
        strategies = corr.meta.get("selected_strategies") or []

        for dr in denial_reasons if isinstance(denial_reasons, list) else []:
            if not isinstance(dr, dict):
                continue
            dtype = str(dr.get("type") or "").strip() or "unknown"
            for s in strategies if isinstance(strategies, list) else []:
                if not isinstance(s, dict):
                    continue
                sid = str(s.get("strategy_id") or "").strip()
                if not sid:
                    continue
                self._learning.log_outcome(
                    db,
                    claim_id=claim_id,
                    denial_type=dtype,
                    root_cause_category=root_cat,
                    strategy_id=sid,
                    outcome=str(outcome_status or ""),
                    meta={"correction_id": corr.id, "resubmission_id": getattr(res, "id", None)},
                )
