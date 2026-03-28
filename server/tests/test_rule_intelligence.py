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
    import app.models.denial  # noqa: F401
    import app.models.rule  # noqa: F401

    ensure_db_initialized()
    if engine is None:
        raise RuntimeError("Database engine was not initialized")
    Base.metadata.create_all(bind=engine)


def _write_json(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")


def _reset_rule_config_caches() -> None:
    import app.layers.rule_intelligence_layer.config as cfg

    cfg._EXTRACTION_CACHE = None
    cfg._NORMALIZATION_CACHE = None
    cfg._CONFIDENCE_CACHE = None
    cfg._SCHEDULER_CACHE = None


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "test_rules.db"
    _bootstrap_test_db(db_path)

    extraction_path = tmp_path / "rule_extraction_patterns.json"
    normalization_path = tmp_path / "rule_normalization.json"
    confidence_path = tmp_path / "rule_confidence.json"

    _write_json(
        extraction_path,
        """{
  "version": "test",
  "rule_types": { "comparators": { "limit": "max" } },
  "patterns": [
    {
      "id": "room_rent",
      "enabled": true,
      "rule_type": "limit",
      "category": "room_rent",
      "tpa_regex": ".*",
      "regex": "(?i)room\\\\s*rent[^\\\\d]{0,60}([0-9][0-9,\\\\.]*\\\\s*(?:k|K)?)\\\\s*(?:/(?:day|night)|per\\\\s*day|per\\\\s*night)?",
      "unit": "INR/day",
      "base_confidence": 0.95,
      "excerpt_context": 50,
      "conditions": { "scope": "general" }
    }
  ]
}""",
    )
    _write_json(
        normalization_path,
        """{
  "version": "test",
  "money": { "multipliers": { "k": 1000 } },
  "units": { "aliases": { "inr/day": "INR/day" } }
}""",
    )
    _write_json(
        confidence_path,
        """{
  "version": "test",
  "default_source_weight": 1.0,
  "source_weights": { "email": 1.0, "pdf": 1.0, "web": 0.6 },
  "min_store_confidence": 0.2,
  "min_use_confidence": 0.7
}""",
    )

    os.environ["RULE_EXTRACTION_PATH"] = str(extraction_path)
    os.environ["RULE_NORMALIZATION_PATH"] = str(normalization_path)
    os.environ["RULE_CONFIDENCE_PATH"] = str(confidence_path)
    _reset_rule_config_caches()

    from fastapi.testclient import TestClient
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def test_rule_ingest_and_validate_and_versioning(client):
    res1 = client.post("/rules/ingest/email", json={"tpa_name": "ACME", "text": "Policy Update: Room rent limit is 5K per day."})
    assert res1.status_code == 200

    res2 = client.post("/validate_rule", json={"tpa": "ACME", "category": "room_rent", "value": 8000, "rule_type": "limit"})
    assert res2.status_code == 200
    payload = res2.json()
    assert payload["valid"] is False
    assert "Exceeds" in payload["reason"]
    assert payload["matched_rule"] is not None
    assert float(payload["matched_rule"]["value"]) == 5000.0
    rule_id = payload["matched_rule"]["id"]

    res3 = client.post("/rules/ingest/email", json={"tpa_name": "ACME", "text": "Policy Update: Room rent limit is 6000 per day."})
    assert res3.status_code == 200

    res4 = client.post("/validate_rule", json={"tpa": "ACME", "category": "room_rent", "value": 8000, "rule_type": "limit"})
    assert res4.status_code == 200
    payload2 = res4.json()
    assert payload2["valid"] is False
    assert payload2["matched_rule"] is not None
    assert float(payload2["matched_rule"]["value"]) == 6000.0

    res_list = client.get("/rules", params={"tpa": "ACME", "category": "room_rent"})
    assert res_list.status_code == 200
    listed = res_list.json()
    assert int(listed.get("total") or 0) >= 1

    res_hist = client.get(f"/rules/{rule_id}/history")
    assert res_hist.status_code == 200
    hist = res_hist.json()
    assert hist.get("rule_id") == rule_id

    from app.db.session import SessionLocal
    from app.models.rule import InsuranceRule, InsuranceRuleHistory

    assert SessionLocal is not None
    db = SessionLocal()
    try:
        rules = db.query(InsuranceRule).all()
        assert len(rules) == 1
        assert int(rules[0].version or 0) >= 2
        hist = db.query(InsuranceRuleHistory).all()
        assert len(hist) >= 1
    finally:
        db.close()


def test_low_confidence_rule_not_used_for_validation(client, tmp_path: Path):
    confidence_path = tmp_path / "rule_confidence_high.json"
    _write_json(
        confidence_path,
        """{
  "version": "test2",
  "default_source_weight": 1.0,
  "source_weights": { "email": 1.0 },
  "min_store_confidence": 0.2,
  "min_use_confidence": 0.99
}""",
    )
    os.environ["RULE_CONFIDENCE_PATH"] = str(confidence_path)
    _reset_rule_config_caches()

    res1 = client.post("/rules/ingest/email", json={"tpa_name": "ACME", "text": "Room rent limit is 5K per day."})
    assert res1.status_code == 200

    res2 = client.post("/validate_rule", json={"tpa": "ACME", "category": "room_rent", "value": 8000, "rule_type": "limit"})
    assert res2.status_code == 200
    payload = res2.json()
    assert payload["valid"] is False
    assert payload["reason"] == "no_high_confidence_rule"
