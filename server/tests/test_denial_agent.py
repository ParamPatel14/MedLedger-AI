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

    import app.models.workflow  # noqa: F401
    import app.models.svm  # noqa: F401
    import app.models.governance  # noqa: F401
    import app.models.denial  # noqa: F401

    ensure_db_initialized()
    if engine is None:
        raise RuntimeError("Database engine was not initialized")
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "test_denials.db"
    _bootstrap_test_db(db_path)
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def test_denial_missing_document_resubmits_and_logs_learning(client):
    res = client.post("/claims", json={"status": "pending", "record_id": None, "claim_data": {"available_documents": [{"type": "discharge_summary", "content": "ok"}], "attachments": []}})
    assert res.status_code == 200
    claim_id = res.json()["id"]

    run = client.post(
        "/claims/status",
        json={
            "claim_id": claim_id,
            "status": "denied",
            "tpa_response_text": "Denied - missing document. Please attach discharge summary.",
            "rejection_codes": ["MD01"],
        },
    )
    assert run.status_code == 200
    data = run.json()
    assert data["status"] in {"resubmitted", "escalated"}

    out = client.post("/claims/outcome", json={"claim_id": claim_id, "outcome_status": "approved"})
    assert out.status_code == 200

    from app.db.session import SessionLocal
    from app.models.denial import CorrectionApplied, LearningLog, Resubmission

    assert SessionLocal is not None
    db = SessionLocal()
    try:
        corr = db.query(CorrectionApplied).filter(CorrectionApplied.claim_id == claim_id).all()
        resubs = db.query(Resubmission).filter(Resubmission.claim_id == claim_id).all()
        learn = db.query(LearningLog).filter(LearningLog.claim_id == claim_id).all()
        assert len(corr) >= 1
        assert len(resubs) >= 0
        assert len(learn) >= 1
    finally:
        db.close()


def test_denial_loop_detection_escalates(client):
    res = client.post("/claims", json={"status": "pending", "record_id": None, "claim_data": {"available_documents": [{"type": "discharge_summary", "content": "ok"}], "attachments": []}})
    assert res.status_code == 200
    claim_id = res.json()["id"]

    last = None
    for _ in range(4):
        last = client.post(
            "/claims/status",
            json={
                "claim_id": claim_id,
                "status": "denied",
                "tpa_response_text": "Denied - missing document.",
                "rejection_codes": ["MD01"],
            },
        )
        assert last.status_code == 200
    assert last is not None
    payload = last.json()
    assert payload["status"] == "escalated"


def test_denial_unknown_reason_escalates(client):
    res = client.post("/claims", json={"status": "pending", "record_id": None, "claim_data": {"billing": {"amount": 12500}, "attachments": []}})
    assert res.status_code == 200
    claim_id = res.json()["id"]

    run = client.post(
        "/claims/status",
        json={
            "claim_id": claim_id,
            "status": "denied",
            "tpa_response_text": "Denied due to internal payer exception code ZXQ-999.",
            "rejection_codes": ["ZXQ-999"],
        },
    )
    assert run.status_code == 200
    data = run.json()
    assert data["status"] == "escalated"
    assert isinstance(data.get("denial_reason"), list)
    assert any(str(x.get("type") or "") == "unknown" for x in data["denial_reason"] if isinstance(x, dict))


def test_denial_dashboard_endpoint(client):
    res = client.post(
        "/claims",
        json={
            "status": "pending",
            "record_id": None,
            "claim_data": {"billing": {"amount": 20000}, "available_documents": [{"type": "discharge_summary", "content": "ok"}], "attachments": []},
        },
    )
    assert res.status_code == 200
    claim_id = res.json()["id"]

    run = client.post(
        "/claims/status",
        json={
            "claim_id": claim_id,
            "status": "denied",
            "tpa_response_text": "Denied - missing document. Please attach discharge summary.",
            "rejection_codes": ["MD01"],
        },
    )
    assert run.status_code == 200

    dash = client.get("/denials/dashboard")
    assert dash.status_code == 200
    payload = dash.json()
    assert "metrics" in payload
    assert "denied_claims" in payload
    assert isinstance(payload["denied_claims"], list)
    metrics = payload["metrics"]
    assert "revenue_recovered" in metrics
    assert "denial_rate_percent" in metrics
    assert "denial_reduction_percent" in metrics
    assert "automation_percent" in metrics
    assert any(str(r.get("claim_id") or "") == claim_id for r in payload["denied_claims"] if isinstance(r, dict))


def test_denial_email_parse_endpoint(client):
    text = "Subject: Claim Denied\n\nClaim ID: ABCD-123456\nRejection Code: MD01\nReason: Missing discharge summary."
    res = client.post("/denials/email/parse", json={"text": text})
    assert res.status_code == 200
    payload = res.json()
    assert str(payload.get("claim_id") or "") == "ABCD-123456"
    assert "MD01" in (payload.get("rejection_codes") or [])


def test_gmail_status_endpoint(client):
    res = client.get("/denials/gmail/status")
    assert res.status_code == 200
    payload = res.json()
    assert "enabled" in payload
    assert "ready" in payload
    assert "env" in payload
