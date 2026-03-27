from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, TypedDict

from sqlalchemy.orm import Session

from app.layers.workflow_layer.agents import ClinicalUnderstandingAgent, CodingAgent, PayerRuleAgent
from app.layers.svm_layer.service import SvmMiddleware
from app.models.workflow import WorkflowState


class WorkflowGraphState(TypedDict, total=False):
    record_id: str
    clinical: dict
    coding: dict
    validation: dict
    svm: dict
    svm_escalated: bool
    confidence: float
    errors: dict
    retries: dict
    current_step: str


def _retry_limit() -> int:
    return 1


def _update_state_row(db: Session, record_id: str, *, step: str, status: str, errors: dict) -> None:
    row = db.query(WorkflowState).filter(WorkflowState.record_id == record_id).first()
    if row is None:
        row = WorkflowState(record_id=record_id, current_step=step, status=status, errors=errors or {})
        db.add(row)
    else:
        row.current_step = step
        row.status = status
        row.errors = errors or {}
    db.commit()


def _inc_retry(state: WorkflowGraphState, step: str) -> int:
    retries = state.get("retries") or {}
    try:
        n = int(retries.get(step, 0))
    except Exception:
        n = 0
    n += 1
    retries[step] = n
    state["retries"] = retries
    return n


@dataclass
class LangGraphOrchestrator:
    clinical_agent: ClinicalUnderstandingAgent
    coding_agent: CodingAgent
    payer_rule_agent: PayerRuleAgent
    svm: SvmMiddleware

    def run(self, db: Session, *, record_id: str, raw_text: str) -> WorkflowGraphState:
        from langgraph.graph import END, StateGraph

        def clinical_node(state: WorkflowGraphState) -> WorkflowGraphState:
            state["current_step"] = "clinical"
            try:
                out = self.clinical_agent.run(db, record_id=record_id, raw_text=raw_text)
                state["clinical"] = out.to_dict()
                state["errors"] = {}
                _update_state_row(db, record_id, step="clinical", status="ok", errors={})
            except Exception as e:
                errors = state.get("errors") or {}
                errors["clinical"] = str(e)
                state["errors"] = errors
                attempt = _inc_retry(state, "clinical")
                status = "retrying" if attempt <= _retry_limit() else "failed"
                _update_state_row(db, record_id, step="clinical", status=status, errors=errors)
            return state

        def svm_after_clinical_node(state: WorkflowGraphState) -> WorkflowGraphState:
            stage = "svm_after_clinical"
            state["current_step"] = stage
            try:
                svm_results = state.get("svm") or {}
                out = self.svm.validate(
                    db,
                    record_id=record_id,
                    stage=stage,
                    agent_name=self.clinical_agent.name,
                    raw_text=raw_text,
                    agent_input={"raw_text": raw_text},
                    agent_output=state.get("clinical") or {},
                    prior_agent_outputs=[],
                    prior_svm_results=[],
                )
                svm_results[stage] = out
                state["svm"] = svm_results
                state["svm_escalated"] = bool(out.get("status") == "escalated" and bool((out.get("decision") or {}).get("trigger_circuit_breaker")))
                state["errors"] = {}
                _update_state_row(db, record_id, step=stage, status="ok", errors={})
            except Exception as e:
                errors = state.get("errors") or {}
                errors[stage] = str(e)
                state["errors"] = errors
                attempt = _inc_retry(state, stage)
                status = "retrying" if attempt <= _retry_limit() else "failed"
                _update_state_row(db, record_id, step=stage, status=status, errors=errors)
            return state

        def coding_node(state: WorkflowGraphState) -> WorkflowGraphState:
            state["current_step"] = "coding"
            try:
                clinical = state.get("clinical") or {}
                out = self.coding_agent.run(
                    db,
                    record_id=record_id,
                    clinical=self.clinical_agent_output_from_dict(clinical),
                    top_k=3,
                )
                state["coding"] = out.to_dict()
                state["errors"] = {}
                _update_state_row(db, record_id, step="coding", status="ok", errors={})
            except Exception as e:
                errors = state.get("errors") or {}
                errors["coding"] = str(e)
                state["errors"] = errors
                attempt = _inc_retry(state, "coding")
                status = "retrying" if attempt <= _retry_limit() else "failed"
                _update_state_row(db, record_id, step="coding", status=status, errors=errors)
            return state

        def svm_after_coding_node(state: WorkflowGraphState) -> WorkflowGraphState:
            stage = "svm_after_coding"
            state["current_step"] = stage
            try:
                svm_results = state.get("svm") or {}
                prior_svm = [svm_results.get("svm_after_clinical")] if isinstance(svm_results, dict) else []
                prior_agent_outputs = [{"agent_name": self.clinical_agent.name, "output": state.get("clinical") or {}}]
                out = self.svm.validate(
                    db,
                    record_id=record_id,
                    stage=stage,
                    agent_name=self.coding_agent.name,
                    raw_text=raw_text,
                    agent_input={"clinical": state.get("clinical") or {}},
                    agent_output=state.get("coding") or {},
                    prior_agent_outputs=prior_agent_outputs,
                    prior_svm_results=[x for x in prior_svm if isinstance(x, dict)],
                )
                svm_results[stage] = out
                state["svm"] = svm_results
                state["svm_escalated"] = bool(out.get("status") == "escalated" and bool((out.get("decision") or {}).get("trigger_circuit_breaker")))
                state["errors"] = {}
                _update_state_row(db, record_id, step=stage, status="ok", errors={})
            except Exception as e:
                errors = state.get("errors") or {}
                errors[stage] = str(e)
                state["errors"] = errors
                attempt = _inc_retry(state, stage)
                status = "retrying" if attempt <= _retry_limit() else "failed"
                _update_state_row(db, record_id, step=stage, status=status, errors=errors)
            return state

        def rule_node(state: WorkflowGraphState) -> WorkflowGraphState:
            state["current_step"] = "payer_rules"
            try:
                clinical = state.get("clinical") or {}
                coding = state.get("coding") or {}
                out = self.payer_rule_agent.run(
                    db,
                    record_id=record_id,
                    clinical=self.clinical_agent_output_from_dict(clinical),
                    coding=self.coding_agent_output_from_dict(coding),
                )
                state["validation"] = out.to_dict()
                state["errors"] = {}
                _update_state_row(db, record_id, step="payer_rules", status="ok", errors={})
            except Exception as e:
                errors = state.get("errors") or {}
                errors["payer_rules"] = str(e)
                state["errors"] = errors
                attempt = _inc_retry(state, "payer_rules")
                status = "retrying" if attempt <= _retry_limit() else "failed"
                _update_state_row(db, record_id, step="payer_rules", status=status, errors=errors)
            return state

        def svm_after_rules_node(state: WorkflowGraphState) -> WorkflowGraphState:
            stage = "svm_after_rules"
            state["current_step"] = stage
            try:
                svm_results = state.get("svm") or {}
                prior_svm = []
                if isinstance(svm_results, dict):
                    for k in ["svm_after_clinical", "svm_after_coding"]:
                        v = svm_results.get(k)
                        if isinstance(v, dict):
                            prior_svm.append(v)
                prior_agent_outputs = [
                    {"agent_name": self.clinical_agent.name, "output": state.get("clinical") or {}},
                    {"agent_name": self.coding_agent.name, "output": state.get("coding") or {}},
                ]
                out = self.svm.validate(
                    db,
                    record_id=record_id,
                    stage=stage,
                    agent_name=self.payer_rule_agent.name,
                    raw_text=raw_text,
                    agent_input={"clinical": state.get("clinical") or {}, "coding": state.get("coding") or {}},
                    agent_output=state.get("validation") or {},
                    prior_agent_outputs=prior_agent_outputs,
                    prior_svm_results=prior_svm,
                )
                svm_results[stage] = out
                state["svm"] = svm_results
                state["svm_escalated"] = bool(out.get("status") == "escalated" and bool((out.get("decision") or {}).get("trigger_circuit_breaker")))
                state["errors"] = {}
                _update_state_row(db, record_id, step=stage, status="ok", errors={})
            except Exception as e:
                errors = state.get("errors") or {}
                errors[stage] = str(e)
                state["errors"] = errors
                attempt = _inc_retry(state, stage)
                status = "retrying" if attempt <= _retry_limit() else "failed"
                _update_state_row(db, record_id, step=stage, status=status, errors=errors)
            return state

        def next_after_clinical(state: WorkflowGraphState) -> str:
            errors = state.get("errors") or {}
            if "clinical" in errors:
                if int((state.get("retries") or {}).get("clinical", 0)) <= _retry_limit():
                    return "clinical"
                return END
            return "svm_after_clinical"

        def next_after_svm_after_clinical(state: WorkflowGraphState) -> str:
            errors = state.get("errors") or {}
            if "svm_after_clinical" in errors:
                if int((state.get("retries") or {}).get("svm_after_clinical", 0)) <= _retry_limit():
                    return "svm_after_clinical"
                return END
            if bool(state.get("svm_escalated")):
                return END
            return "coding"

        def next_after_coding(state: WorkflowGraphState) -> str:
            errors = state.get("errors") or {}
            if "coding" in errors:
                if int((state.get("retries") or {}).get("coding", 0)) <= _retry_limit():
                    return "coding"
                return END
            return "svm_after_coding"

        def next_after_svm_after_coding(state: WorkflowGraphState) -> str:
            errors = state.get("errors") or {}
            if "svm_after_coding" in errors:
                if int((state.get("retries") or {}).get("svm_after_coding", 0)) <= _retry_limit():
                    return "svm_after_coding"
                return END
            if bool(state.get("svm_escalated")):
                return END
            return "payer_rules"

        def next_after_rules(state: WorkflowGraphState) -> str:
            errors = state.get("errors") or {}
            if "payer_rules" in errors:
                if int((state.get("retries") or {}).get("payer_rules", 0)) <= _retry_limit():
                    return "payer_rules"
                return END
            return "svm_after_rules"

        def next_after_svm_after_rules(state: WorkflowGraphState) -> str:
            errors = state.get("errors") or {}
            if "svm_after_rules" in errors:
                if int((state.get("retries") or {}).get("svm_after_rules", 0)) <= _retry_limit():
                    return "svm_after_rules"
                return END
            return END

        graph = StateGraph(WorkflowGraphState)
        graph.add_node("clinical", clinical_node)
        graph.add_node("svm_after_clinical", svm_after_clinical_node)
        graph.add_node("coding", coding_node)
        graph.add_node("svm_after_coding", svm_after_coding_node)
        graph.add_node("payer_rules", rule_node)
        graph.add_node("svm_after_rules", svm_after_rules_node)
        graph.set_entry_point("clinical")
        graph.add_conditional_edges(
            "clinical",
            next_after_clinical,
            {"clinical": "clinical", "svm_after_clinical": "svm_after_clinical", END: END},
        )
        graph.add_conditional_edges(
            "svm_after_clinical",
            next_after_svm_after_clinical,
            {"svm_after_clinical": "svm_after_clinical", "coding": "coding", END: END},
        )
        graph.add_conditional_edges(
            "coding",
            next_after_coding,
            {"coding": "coding", "svm_after_coding": "svm_after_coding", END: END},
        )
        graph.add_conditional_edges(
            "svm_after_coding",
            next_after_svm_after_coding,
            {"svm_after_coding": "svm_after_coding", "payer_rules": "payer_rules", END: END},
        )
        graph.add_conditional_edges(
            "payer_rules",
            next_after_rules,
            {"payer_rules": "payer_rules", "svm_after_rules": "svm_after_rules", END: END},
        )
        graph.add_conditional_edges(
            "svm_after_rules",
            next_after_svm_after_rules,
            {"svm_after_rules": "svm_after_rules", END: END},
        )
        app = graph.compile()

        initial: WorkflowGraphState = {
            "record_id": record_id,
            "errors": {},
            "retries": {},
            "current_step": "clinical",
            "svm": {},
            "svm_escalated": False,
        }
        _update_state_row(db, record_id, step="clinical", status="running", errors={})
        final = app.invoke(initial)

        clinical_conf = float((final.get("clinical") or {}).get("confidence") or 0.0)
        coding_conf = float((final.get("coding") or {}).get("confidence") or 0.0)
        rule_conf = float((final.get("validation") or {}).get("confidence") or 0.0)
        overall = max(0.0, min(1.0, (clinical_conf + coding_conf + rule_conf) / 3.0)) if rule_conf or coding_conf or clinical_conf else 0.0
        final["confidence"] = overall

        errors = final.get("errors") or {}
        status = "failed" if errors else "completed"
        step = str(final.get("current_step") or "done")
        _update_state_row(db, record_id, step=step, status=status, errors=errors)
        return final

    @staticmethod
    def clinical_agent_output_from_dict(d: Dict[str, Any]):
        from app.layers.workflow_layer.agents import ClinicalUnderstandingOut

        return ClinicalUnderstandingOut(
            diagnosis=list(d.get("diagnosis") or []),
            procedures=list(d.get("procedures") or []),
            confidence=float(d.get("confidence") or 0.0),
            explanation=str(d.get("explanation") or ""),
        )

    @staticmethod
    def coding_agent_output_from_dict(d: Dict[str, Any]):
        from app.layers.workflow_layer.agents import CodingOut

        return CodingOut(
            icd_codes=list(d.get("icd_codes") or []),
            mapping_reason=str(d.get("mapping_reason") or ""),
            confidence=float(d.get("confidence") or 0.0),
        )
