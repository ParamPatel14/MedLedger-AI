from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest


def _repo_server_root() -> Path:
    return Path(__file__).resolve().parents[1]


SERVER_ROOT = _repo_server_root()
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


def _reset_db_engine(db_url: str) -> None:
    os.environ["DATABASE_URL"] = db_url
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["GEMINI_MODEL"] = ""
    os.environ["GEMINI_VISION_MODEL"] = ""

    import app.db.session as session

    session.DATABASE_URL = None
    session.engine = None
    session.engine_init_error = None
    session.SessionLocal = None
    session._init_engine()


def _bootstrap_test_db(db_path: Path) -> None:
    _reset_db_engine(f"sqlite:///{db_path.as_posix()}")
    from app.db.base import Base
    from app.db.session import ensure_db_initialized, engine

    import app.models.denial  # noqa: F401
    import app.models.governance  # noqa: F401
    import app.models.svm  # noqa: F401
    import app.models.workflow  # noqa: F401

    ensure_db_initialized()
    if engine is None:
        raise RuntimeError("Database engine was not initialized")
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "test_oneclick.db"
    _bootstrap_test_db(db_path)
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def _poll(client, run_id: str, *, max_wait_s: float = 2.0) -> dict:
    started = time.time()
    last = {}
    while time.time() - started < max_wait_s:
        res = client.get(f"/process/oneclick/{run_id}")
        assert res.status_code == 200
        last = res.json()
        if last.get("status") in {"done", "needs_review", "error"}:
            return last
        time.sleep(0.01)
    return last


def test_oneclick_workflow_happy_path_approves(client, monkeypatch):
    import app.api.routes.process as process_routes

    def fake_orchestrator_run(self, db, record_id: str, raw_text: str):
        return {
            "clinical": {"patient": {"name": "Test Patient"}, "diagnoses": ["Peritonitis"]},
            "coding": {"icd_codes": [{"system": "ICD10", "code": "K659", "description": "Peritonitis, unspecified", "score": 0.95}]},
            "validation": {"is_valid": True, "issues": []},
            "svm": {"summary": {"overall": "pass"}},
            "governance": {"decision": "APPROVE"},
            "errors": {},
        }

    monkeypatch.setattr(process_routes.LangGraphOrchestrator, "run", fake_orchestrator_run, raising=True)
    monkeypatch.setattr(process_routes.SvmMiddleware, "overall_status", staticmethod(lambda _svm: "pass"), raising=True)
    monkeypatch.setattr(process_routes, "_simulate_denial_reason", lambda _claim_data: "", raising=True)

    res = client.post("/process/oneclick/start", json={"text": "test claim", "auto_call_if_needed": False})
    assert res.status_code == 200
    rid = res.json().get("run_id")
    assert isinstance(rid, str) and rid

    out = _poll(client, rid, max_wait_s=2.0)
    assert out.get("status") == "done"
    assert out.get("step") == "approved"
    assert out.get("decision") == "APPROVE"
    assert isinstance(out.get("claim_id"), str) and out.get("claim_id")


def test_oneclick_workflow_denial_then_resubmit_then_approve(client, monkeypatch):
    import app.api.routes.process as process_routes
    import app.layers.denial_layer.service as denial_service
    from app.models.denial import Claim as ClaimModel

    def fake_orchestrator_run(self, db, record_id: str, raw_text: str):
        return {
            "clinical": {"patient": {"name": "Test Patient"}, "diagnoses": ["Type 2 diabetes mellitus"]},
            "coding": {"icd_codes": [{"system": "ICD10", "code": "E119", "description": "Type 2 diabetes mellitus without complications", "score": 0.95}]},
            "validation": {"is_valid": True, "issues": []},
            "svm": {"summary": {"overall": "pass"}},
            "governance": {"decision": "APPROVE"},
            "errors": {},
        }

    def fake_run_for_denial_event(self, db, claim_id: str, denial_event_id: int):
        return {"status": "resubmitted", "audit": {"claim_id": claim_id, "denial_event_id": denial_event_id}}

    def fake_record_outcome(self, db, claim_id: str, outcome_status: str):
        row = db.query(ClaimModel).filter(ClaimModel.id == claim_id).first()
        assert row is not None
        row.status = str(outcome_status)
        db.commit()
        return {"ok": True, "claim_id": claim_id, "status": outcome_status}

    monkeypatch.setattr(process_routes.LangGraphOrchestrator, "run", fake_orchestrator_run, raising=True)
    monkeypatch.setattr(process_routes.SvmMiddleware, "overall_status", staticmethod(lambda _svm: "pass"), raising=True)
    monkeypatch.setattr(process_routes, "_simulate_denial_reason", lambda _claim_data: "Denied - missing document. Please attach discharge summary.", raising=True)
    monkeypatch.setattr(denial_service.DenialManagementAgent, "run_for_denial_event", fake_run_for_denial_event, raising=True)
    monkeypatch.setattr(denial_service.DenialManagementAgent, "record_outcome", fake_record_outcome, raising=True)

    res = client.post("/process/oneclick/start", json={"text": "test claim", "auto_call_if_needed": False})
    assert res.status_code == 200
    rid = res.json().get("run_id")
    assert isinstance(rid, str) and rid

    out = _poll(client, rid, max_wait_s=2.0)
    assert out.get("status") == "done"
    assert out.get("step") == "approved"
    assert isinstance(out.get("claim_id"), str) and out.get("claim_id")
    assert isinstance(out.get("denial_event_id"), int)


def test_oneclick_workflow_override_guardrails_continues(client, monkeypatch):
    import app.api.routes.process as process_routes

    def fake_orchestrator_run(self, db, record_id: str, raw_text: str):
        return {
            "clinical": {"diagnosis": ["Appendicitis"], "procedures": ["Appendectomy"], "confidence": 0.8, "explanation": "demo"},
            "coding": {"icd_codes": [{"system": "ICD10", "code": "K35", "description": "Acute appendicitis", "score": 0.75}], "confidence": 0.7},
            "validation": {"is_valid": True, "issues": [], "confidence": 0.9},
            "svm": {"svm_after_clinical": {"status": "review", "scores": {"source_alignment": 0.2, "consistency": 0.2, "reasonability": 0.2}}},
            "governance": {"decision": "BLOCK", "confidence": 0.4, "issues": [{"type": "demo_block", "severity": "critical", "message": "blocked for demo"}]},
            "errors": {},
        }

    monkeypatch.setattr(process_routes.LangGraphOrchestrator, "run", fake_orchestrator_run, raising=True)
    monkeypatch.setattr(process_routes.SvmMiddleware, "overall_status", staticmethod(lambda _svm: "review"), raising=True)
    monkeypatch.setattr(process_routes, "_simulate_denial_reason", lambda _claim_data: "", raising=True)

    res = client.post("/process/oneclick/start", json={"text": "test claim", "auto_call_if_needed": False})
    assert res.status_code == 200
    rid = res.json().get("run_id")
    assert isinstance(rid, str) and rid
    out = _poll(client, rid, max_wait_s=2.0)
    assert out.get("status") == "needs_review"

    res2 = client.post(f"/process/oneclick/{rid}/override")
    assert res2.status_code == 200
    out2 = _poll(client, rid, max_wait_s=2.0)
    assert out2.get("status") == "done"
    assert out2.get("step") == "approved"
