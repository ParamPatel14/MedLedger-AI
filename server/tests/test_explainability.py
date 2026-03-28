from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def _repo_server_root() -> Path:
    return Path(__file__).resolve().parents[1]


SERVER_ROOT = _repo_server_root()
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


def _reset_db_engine(db_url: str) -> None:
    os.environ["DATABASE_URL"] = db_url
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

    import app.models.workflow  # noqa: F401
    import app.models.svm  # noqa: F401
    import app.models.governance  # noqa: F401
    import app.models.explainability  # noqa: F401

    ensure_db_initialized()
    if engine is None:
        raise RuntimeError("Database engine was not initialized")
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db_session(tmp_path: Path):
    db_path = tmp_path / "test_explainability.db"
    _bootstrap_test_db(db_path)

    from app.db.session import SessionLocal

    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "test_explainability_api.db"
    _bootstrap_test_db(db_path)
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def test_explainability_service_generates_and_persists_audit(db_session):
    from app.layers.explainability_layer.service import ExplainabilityService
    from app.models.governance import GovernanceAuditLog
    from app.models.svm import SvmAuditLog
    from app.models.workflow import AgentOutput, WorkflowRecord
    from app.models.explainability import ExplainabilityAuditTrail

    record = WorkflowRecord(raw_text="Patient has diabetes. Room rent limit noted.")
    db_session.add(record)
    db_session.commit()

    clinical = {"diagnosis": ["diabetes"], "procedures": [], "confidence": 0.92, "explanation": ""}
    coding = {"icd_codes": [{"code": "E11", "score": 0.88, "source_text": "diabetes"}], "confidence": 0.88, "mapping_reason": ""}
    validation = {"is_valid": False, "issues": [{"type": "exceeds_limit", "severity": "warning", "message": ""}], "confidence": 0.74}
    svm = {
        "svm_after_clinical": {"status": "pass", "confidence": 0.91, "scores": {"source_alignment": 0.92, "consistency": 0.88, "reasonability": 0.9}},
        "svm_after_coding": {"status": "pass", "confidence": 0.89, "scores": {"source_alignment": 0.9, "consistency": 0.87, "reasonability": 0.88}},
    }
    governance = {"decision": "WARN", "confidence": 0.87, "reason": "Warnings present", "issues": []}

    db_session.add(AgentOutput(record_id=record.id, agent_name="clinical_understanding", input={}, output=clinical, confidence=0.92))
    db_session.add(AgentOutput(record_id=record.id, agent_name="coding", input={}, output=coding, confidence=0.88))
    db_session.add(AgentOutput(record_id=record.id, agent_name="payer_rules", input={}, output=validation, confidence=0.74))
    db_session.add(SvmAuditLog(record_id=record.id, stage="svm_after_clinical", agent_name="clinical_understanding", agent_input={}, agent_output=clinical, claims=[], scores=svm["svm_after_clinical"]["scores"], status="pass", confidence=0.91, decision={}, issues=[], explanations=[]))
    db_session.add(SvmAuditLog(record_id=record.id, stage="svm_after_coding", agent_name="coding", agent_input={}, agent_output=coding, claims=[], scores=svm["svm_after_coding"]["scores"], status="pass", confidence=0.89, decision={}, issues=[], explanations=[]))
    db_session.add(GovernanceAuditLog(record_id=record.id, decision="WARN", confidence=0.87, reason="Warnings present", issues=[], payload={}))
    db_session.commit()

    svc = ExplainabilityService()
    out = svc.build_and_store(
        db_session,
        record_id=record.id,
        raw_text=str(record.raw_text),
        clinical=clinical,
        coding=coding,
        validation=validation,
        svm=svm,
        governance=governance,
        workflow_confidence=0.85,
    )

    assert out["decision"] == "WARN"
    assert float(out["confidence"]) > 0.0
    assert out["audit_id"]
    assert out["trace"]["trace_id"] == record.id
    assert isinstance(out["explanations"], list)
    assert any("Diagnosis 'diabetes'" in str(x.get("explanation") or "") for x in out["explanations"])

    row = db_session.query(ExplainabilityAuditTrail).filter(ExplainabilityAuditTrail.audit_id == out["audit_id"]).first()
    assert row is not None
    assert row.record_id == record.id


def test_process_explain_endpoint_returns_structured_output(client):
    res = client.post("/process/explain", json={"text": "Patient has diabetes and hypertension. Room rent limit noted."})
    assert res.status_code == 200
    payload = res.json()
    assert str(payload.get("decision") or "")
    assert float(payload.get("confidence") or 0.0) >= 0.0
    assert str(payload.get("audit_id") or "")
    assert isinstance(payload.get("trace"), dict)
    assert isinstance(payload.get("explanations"), list)
    if payload.get("explanations"):
        item = payload["explanations"][0]
        assert "type" in item
        assert "explanation" in item
        assert "confidence" in item
        assert "details" in item
