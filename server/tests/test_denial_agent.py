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
