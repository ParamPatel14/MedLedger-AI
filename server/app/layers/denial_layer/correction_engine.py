from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.layers.denial_layer.learning import LearningService, StrategyPrior
from app.layers.denial_layer.utils import (
    JsonPatchOp,
    append_path,
    deep_copy,
    delete_path,
    filter_list_in_place,
    get_path,
    set_path,
)
from app.layers.governance_layer.evaluation import DecisionInputs, evaluate_condition, get_values
from app.layers.workflow_layer.agents import ClinicalUnderstandingOut, CodingAgent


@dataclass(frozen=True)
class StrategySelection:
    strategy_id: str
    category: str
    confidence: float
    prior: StrategyPrior
    actions: List[dict]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "category": self.category,
            "confidence": float(self.confidence),
            "prior": self.prior.to_dict(),
            "actions": self.actions,
        }


@dataclass(frozen=True)
class CorrectionResult:
    updated_claim_data: Dict[str, Any]
    patch: List[JsonPatchOp]
    selections: List[StrategySelection]
    issues: List[Dict[str, Any]]
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated_claim_data": self.updated_claim_data,
            "patch": [p.to_dict() for p in self.patch],
            "selections": [s.to_dict() for s in self.selections],
            "issues": self.issues,
            "confidence": float(self.confidence),
        }


class CorrectionEngine:
    def __init__(self) -> None:
        self._learning = LearningService()
        self._coding_agent = CodingAgent()

    def _make_inputs(self, ctx: Dict[str, Any], denial_reason_types: List[str], confidence: float) -> DecisionInputs:
        external_issues = [{"type": t, "severity": "info"} for t in denial_reason_types if str(t or "").strip()]
        return DecisionInputs(
            raw_text=str(ctx.get("raw_text") or ""),
            workflow_confidence=float(confidence or 0.0),
            svm=ctx.get("svm") if isinstance(ctx.get("svm"), dict) else {},
            policy_issues=[],
            edge_issues=[],
            external_issues=external_issues,
        )

    def _select_strategy(
        self,
        db: Session,
        *,
        rules_cfg: Dict[str, Any],
        thresholds_cfg: Dict[str, Any],
        ctx: Dict[str, Any],
        denial_type: str,
        root_cause_category: str,
        workflow_confidence: float,
    ) -> Optional[StrategySelection]:
        strategies = rules_cfg.get("strategies") or []
        if not isinstance(strategies, list):
            strategies = []

        decision_inputs = self._make_inputs(ctx, [denial_type], workflow_confidence)
        best: Optional[StrategySelection] = None
        for s in strategies:
            if not isinstance(s, dict):
                continue
            cond = s.get("when") or {}
            if not isinstance(cond, dict):
                continue
            if not evaluate_condition(cond, ctx={"thresholds": thresholds_cfg, **ctx}, decision_inputs=decision_inputs):
                continue
            sid = str(s.get("id") or "").strip()
            cat = str(s.get("category") or "").strip() or "unknown"
            base_conf = float(s.get("base_confidence") or 0.0)
            prior = self._learning.compute_strategy_prior(
                db,
                denial_type=str(denial_type or ""),
                root_cause_category=str(root_cause_category or ""),
                strategy_id=sid,
                thresholds_cfg=thresholds_cfg,
            )
            score = min(1.0, max(0.0, base_conf + float(prior.boost)))
            actions = s.get("actions") or []
            if not isinstance(actions, list):
                actions = []
            selection = StrategySelection(strategy_id=sid, category=cat, confidence=score, prior=prior, actions=actions)
            if best is None or selection.confidence > best.confidence:
                best = selection
        return best

    def _execute_actions(
        self,
        db: Session,
        *,
        claim_record_id: Optional[str],
        ctx: Dict[str, Any],
        claim_data: Dict[str, Any],
        selection: StrategySelection,
        thresholds_cfg: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[JsonPatchOp], List[Dict[str, Any]]]:
        updated = deep_copy(claim_data) if isinstance(claim_data, dict) else {}
        patch_ops: List[JsonPatchOp] = []
        issues: List[Dict[str, Any]] = []

        for a in selection.actions:
            if not isinstance(a, dict):
                continue
            kind = str(a.get("kind") or "").strip()
            if kind == "set_value":
                path = str(a.get("path") or "").strip()
                value = a.get("value")
                wrap = {"claim": {"claim_data": updated}}
                patch_ops.extend(set_path(wrap, path, value))
                updated = wrap.get("claim", {}).get("claim_data") or updated
                continue
            if kind == "delete_value":
                path = str(a.get("path") or "").strip()
                wrap = {"claim": {"claim_data": updated}}
                patch_ops.extend(delete_path(wrap, path))
                updated = wrap.get("claim", {}).get("claim_data") or updated
                continue
            if kind == "append_value":
                path = str(a.get("path") or "").strip()
                value = a.get("value")
                wrap = {"claim": {"claim_data": updated}}
                patch_ops.extend(append_path(wrap, path, value))
                updated = wrap.get("claim", {}).get("claim_data") or updated
                continue
            if kind == "attach_document":
                available_path = str(a.get("available_path") or "").strip()
                attachments_path = str(a.get("attachments_path") or "").strip()
                doc_type = str(a.get("doc_type") or "").strip()
                doc_type_field = str(a.get("doc_type_field") or "type").strip() or "type"

                wrap = {"claim": {"claim_data": updated}}
                docs = get_values(wrap, available_path)
                chosen = None
                for d in docs:
                    if not isinstance(d, dict):
                        continue
                    if str(d.get(doc_type_field) or "").strip() == doc_type:
                        chosen = d
                        break
                if chosen is None:
                    issues.append({"type": "missing_document", "severity": "warning", "message": f"Document not found: {doc_type}"})
                    continue
                patch_ops.extend(append_path(wrap, attachments_path, chosen))
                updated = wrap.get("claim", {}).get("claim_data") or updated
                continue
            if kind == "filter_list":
                path = str(a.get("path") or "").strip()
                keep_when = a.get("keep_when") or {}
                if not isinstance(keep_when, dict):
                    continue
                wrap = {"claim": {"claim_data": updated}}
                target = get_path(wrap, path)
                if not isinstance(target, list):
                    continue
                items = target
                mask: List[bool] = []
                for item in items:
                    item_ctx = {"item": item, **ctx, "claim": {"claim_data": updated}, "thresholds": thresholds_cfg}
                    decision_inputs = self._make_inputs(ctx, [], float(ctx.get("confidence") or 0.0))
                    mask.append(bool(evaluate_condition(keep_when, ctx=item_ctx, decision_inputs=decision_inputs)))
                patch_ops.extend(filter_list_in_place(wrap, path, mask))
                updated = wrap.get("claim", {}).get("claim_data") or updated
                continue
            if kind == "rerun_coding":
                clinical_path = str(a.get("clinical_path") or "").strip()
                target_path = str(a.get("target_path") or "").strip()
                wrap = {"claim": {"claim_data": updated}}
                clinical_dict = get_values(wrap, clinical_path)
                if len(clinical_dict) != 1 or not isinstance(clinical_dict[0], dict):
                    issues.append({"type": "missing_clinical", "severity": "warning", "message": "Clinical data missing for rerun_coding"})
                    continue
                if not claim_record_id:
                    issues.append({"type": "missing_record_id", "severity": "warning", "message": "record_id missing; rerun_coding requires record-backed claim"})
                    continue
                cd = clinical_dict[0]
                clinical = ClinicalUnderstandingOut(
                    diagnosis=cd.get("diagnosis") or [],
                    procedures=cd.get("procedures") or [],
                    confidence=float(cd.get("confidence") or 0.0),
                    explanation=str(cd.get("explanation") or ""),
                )
                coding_out = self._coding_agent.run(db, record_id=claim_record_id, clinical=clinical, top_k=int(a.get("top_k") or 3))
                patch_ops.extend(set_path(wrap, target_path, coding_out.to_dict()))
                updated = wrap.get("claim", {}).get("claim_data") or updated
                continue

        return updated, patch_ops, issues

    def apply(
        self,
        db: Session,
        *,
        rules_cfg: Dict[str, Any],
        thresholds_cfg: Dict[str, Any],
        ctx: Dict[str, Any],
        claim_record_id: Optional[str],
        claim_data: Dict[str, Any],
        denial_reasons: List[Dict[str, Any]],
        root_cause: Dict[str, Any],
        workflow_confidence: float,
    ) -> CorrectionResult:
        selections: List[StrategySelection] = []
        patch_ops: List[JsonPatchOp] = []
        issues: List[Dict[str, Any]] = []
        updated = deep_copy(claim_data) if isinstance(claim_data, dict) else {}

        rc_category = str(root_cause.get("category") or "").strip() or "unknown"
        for r in denial_reasons:
            dtype = str(r.get("type") or "").strip() or "unknown"
            selection = self._select_strategy(
                db,
                rules_cfg=rules_cfg,
                thresholds_cfg=thresholds_cfg,
                ctx={**ctx, "claim": {"claim_data": updated}},
                denial_type=dtype,
                root_cause_category=rc_category,
                workflow_confidence=workflow_confidence,
            )
            if selection is None:
                issues.append({"type": "no_strategy", "severity": "warning", "message": f"No strategy matched for {dtype}"})
                continue
            selections.append(selection)
            updated, ops, step_issues = self._execute_actions(
                db,
                claim_record_id=claim_record_id,
                ctx={**ctx, "claim": {"claim_data": updated}},
                claim_data=updated,
                selection=selection,
                thresholds_cfg=thresholds_cfg,
            )
            patch_ops.extend(ops)
            issues.extend(step_issues)

        confidence = 0.0
        if selections:
            confidence = sum(s.confidence for s in selections) / len(selections)
        return CorrectionResult(updated_claim_data=updated, patch=patch_ops, selections=selections, issues=issues, confidence=confidence)
