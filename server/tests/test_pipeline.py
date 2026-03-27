from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _repo_server_root() -> Path:
    return Path(__file__).resolve().parents[1]


SERVER_ROOT = _repo_server_root()
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


def _tmp_dir() -> Path:
    d = SERVER_ROOT / ".tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_payer_rules() -> Dict[str, Any]:
    path = SERVER_ROOT / "app" / "config" / "payer_rules.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}



def _thresholds_from_rules(rules: Dict[str, Any]) -> Tuple[float, float]:
    thr = rules.get("thresholds") if isinstance(rules.get("thresholds"), dict) else {}
    try:
        min_icd_similarity = float(thr.get("min_icd_similarity", 0.65))
    except Exception:
        min_icd_similarity = 0.65
    try:
        high_conf = float(thr.get("high_confidence_threshold", 0.85))
    except Exception:
        high_conf = 0.85
    return min_icd_similarity, high_conf


def _status_from_trace(trace: Dict[str, Any]) -> str:
    payer = trace.get("payer") or {}
    issues = payer.get("issues") or []
    if not isinstance(issues, list):
        issues = []
    severities = [str(i.get("severity") or "").lower() for i in issues if isinstance(i, dict)]
    if "critical" in severities or bool(payer.get("is_valid")) is False:
        return "rejected"
    if any(s in {"warning", "error"} for s in severities):
        return "review"
    return "approved"


def _extract_codes(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    coding = trace.get("coding") or {}
    codes = coding.get("icd_codes") or []
    if not isinstance(codes, list):
        return []
    out: List[Dict[str, Any]] = []
    for c in codes:
        if isinstance(c, dict):
            out.append(c)
    return out


def _code_prefixes(codes: List[Dict[str, Any]], *, min_icd_similarity: float) -> List[str]:
    prefixes: List[str] = []
    for c in codes:
        try:
            score = float(c.get("score") or 0.0)
        except Exception:
            score = 0.0
        if score < min_icd_similarity:
            continue
        code = str(c.get("code") or "").strip().upper()
        if not code:
            continue
        prefix = code.split(".")[0]
        prefixes.append(prefix)
    return prefixes


def _issue_types(trace: Dict[str, Any]) -> List[str]:
    payer = trace.get("payer") or {}
    issues = payer.get("issues") or []
    if not isinstance(issues, list):
        return []
    out: List[str] = []
    for it in issues:
        if not isinstance(it, dict):
            continue
        sev = str(it.get("severity") or "").lower().strip()
        if sev and sev not in {"warning", "error", "critical"}:
            continue
        t = str(it.get("type") or "").strip()
        if t:
            out.append(t)
    return out


@dataclass(frozen=True)
class TestCase:
    input: str
    expected_status: str
    expected_icd: List[str]
    expected_flags: List[str]


def build_test_dataset() -> List[TestCase]:
    raw: List[Dict[str, Any]] = [
        {
            "input": "Type 2 diabetes mellitus with high blood sugar levels.",
            "expected_status": "approved",
            "expected_icd": ["E11", "R73"],
            "expected_flags": [],
        },
        {
            "input": "Asthma with difficulty breathing.",
            "expected_status": "approved",
            "expected_icd": ["J45"],
            "expected_flags": [],
        },
        {
            "input": "Urinary tract infection (UTI).",
            "expected_status": "approved",
            "expected_icd": ["N39"],
            "expected_flags": [],
        },
        {
            "input": "Myocardial infarction / heart attack symptoms.",
            "expected_status": "approved",
            "expected_icd": ["I21"],
            "expected_flags": [],
        },
        {
            "input": "Chest pain since morning.",
            "expected_status": "approved",
            "expected_icd": ["R07"],
            "expected_flags": [],
        },
        {
            "input": "Possible hypertension. Monitor BP.",
            "expected_status": "review",
            "expected_icd": [],
            "expected_flags": ["ambiguous_terms"],
        },
        {
            "input": "Rule out asthma; shortness of breath.",
            "expected_status": "review",
            "expected_icd": ["J45"],
            "expected_flags": ["ambiguous_terms"],
        },
        {
            "input": "HTN and chest pain.",
            "expected_status": "review",
            "expected_icd": ["R07"],
            "expected_flags": ["diagnosis_code_mismatch"],
        },
        {
            "input": "Type 2 diabetes and asthma.",
            "expected_status": "approved",
            "expected_icd": ["E11", "J45"],
            "expected_flags": [],
        },
        {
            "input": "Type 2 diabetes, urinary tract infection, and asthma flare.",
            "expected_status": "approved",
            "expected_icd": ["E11", "N39", "J45"],
            "expected_flags": [],
        },
        {
            "input": "Type 1 diabetes mellitus and type 2 diabetes mellitus documented together.",
            "expected_status": "rejected",
            "expected_icd": ["E10", "E11"],
            "expected_flags": ["mutually_exclusive"],
        },
        {
            "input": "Asthma and COPD exacerbation.",
            "expected_status": "review",
            "expected_icd": ["J45", "J44"],
            "expected_flags": ["incompatible_codes"],
        },
        {
            "input": "Dialysis session today.",
            "expected_status": "rejected",
            "expected_icd": [],
            "expected_flags": ["procedure_requires_diagnosis"],
        },
        {
            "input": "Dialysis for chronic kidney disease stage 3.",
            "expected_status": "approved",
            "expected_icd": ["N18"],
            "expected_flags": [],
        },
        {
            "input": "Angioplasty performed yesterday.",
            "expected_status": "rejected",
            "expected_icd": [],
            "expected_flags": ["procedure_requires_diagnosis"],
        },
        {
            "input": "Angioplasty for coronary artery disease.",
            "expected_status": "approved",
            "expected_icd": ["I25"],
            "expected_flags": [],
        },
        {
            "input": "Insulin therapy started. Type 2 diabetes mellitus.",
            "expected_status": "approved",
            "expected_icd": ["E11"],
            "expected_flags": [],
        },
        {
            "input": "Insulin therapy started without diabetes diagnosis.",
            "expected_status": "review",
            "expected_icd": [],
            "expected_flags": ["procedure_requires_diagnosis"],
        },
        {
            "input": "Long-term insulin use (Z79.4) without diabetes diagnosis.",
            "expected_status": "rejected",
            "expected_icd": ["Z79"],
            "expected_flags": ["missing_supporting_diagnosis"],
        },
        {
            "input": "Long-term insulin use (Z79.4) with type 2 diabetes mellitus.",
            "expected_status": "approved",
            "expected_icd": ["Z79", "E11"],
            "expected_flags": [],
        },
        {
            "input": "Dependence on renal dialysis (Z99.2) without CKD documented.",
            "expected_status": "rejected",
            "expected_icd": ["Z99"],
            "expected_flags": ["missing_supporting_diagnosis"],
        },
        {
            "input": "Dependence on renal dialysis (Z99.2) with chronic kidney disease stage 3.",
            "expected_status": "approved",
            "expected_icd": ["Z99", "N18"],
            "expected_flags": [],
        },
        {"input": "Xylofibrosis.", "expected_status": "review", "expected_icd": [], "expected_flags": ["ambiguous_diagnosis"]},
        {
            "input": "Probable unknown viral syndrome with fever.",
            "expected_status": "review",
            "expected_icd": [],
            "expected_flags": ["ambiguous_terms"],
        },
        {
            "input": "Questionable myocardial infarction, chest pain present.",
            "expected_status": "review",
            "expected_icd": ["R07"],
            "expected_flags": ["ambiguous_terms"],
        },
    ]
    out: List[TestCase] = []
    for item in raw:
        out.append(
            TestCase(
                input=str(item["input"]),
                expected_status=str(item["expected_status"]),
                expected_icd=list(item.get("expected_icd") or []),
                expected_flags=list(item.get("expected_flags") or []),
            )
        )
    if len(out) < 25:
        raise RuntimeError("Test dataset must include at least 25 cases")
    return out[:25]


def _bootstrap_test_db(db_path: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["GEMINI_MODEL"] = ""
    os.environ["GEMINI_VISION_MODEL"] = ""

    from app.db.base import Base
    from app.db.session import ensure_db_initialized, engine

    import app.models.workflow  # noqa: F401
    import app.models.svm  # noqa: F401

    ensure_db_initialized()
    if engine is None:
        raise RuntimeError("Database engine was not initialized")
    Base.metadata.create_all(bind=engine)


def _run_trace(text: str) -> Dict[str, Any]:
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    res = client.post("/process/trace", json={"text": text})
    if int(getattr(res, "status_code", 0) or 0) >= 400:
        raise RuntimeError(f"Trace request failed: {res.status_code} {res.text}")
    return res.json()


def _match_expected_prefixes(actual_prefixes: List[str], expected_prefixes: List[str]) -> bool:
    if not expected_prefixes:
        return True
    s = set(actual_prefixes)
    for exp in expected_prefixes:
        e = str(exp or "").strip().upper()
        if not e:
            continue
        if not any(p.startswith(e) for p in s):
            return False
    return True


def _flags_present(actual_flags: List[str], expected_flags: List[str]) -> bool:
    if not expected_flags:
        return True
    s = set(actual_flags)
    return all(str(f).strip() in s for f in expected_flags if str(f).strip())


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end agentic pipeline tests.")
    parser.add_argument("--verbose", action="store_true", help="Print per-agent outputs for every case.")
    parser.add_argument("--save-json", action="store_true", help="Save report JSON under server/.tmp/test_report.json.")
    args = parser.parse_args(argv)

    payer_rules = _load_payer_rules()
    min_icd_similarity, _high_conf = _thresholds_from_rules(payer_rules)

    db_path = _tmp_dir() / "test_pipeline.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass
    _bootstrap_test_db(db_path)

    dataset = build_test_dataset()
    total = len(dataset)

    passed = 0
    failed: List[Dict[str, Any]] = []

    icd_cases = 0
    icd_correct = 0

    edge_expected = 0
    edge_correct = 0

    for idx, tc in enumerate(dataset, start=1):
        trace = _run_trace(tc.input)
        actual_status = _status_from_trace(trace)
        codes = _extract_codes(trace)
        prefixes = _code_prefixes(codes, min_icd_similarity=min_icd_similarity)
        actual_flags = _issue_types(trace)

        status_ok = actual_status == tc.expected_status
        icd_ok = _match_expected_prefixes(prefixes, tc.expected_icd)
        flags_ok = _flags_present(actual_flags, tc.expected_flags)

        if tc.expected_icd:
            icd_cases += 1
            if icd_ok:
                icd_correct += 1

        if tc.expected_flags:
            edge_expected += 1
            if flags_ok:
                edge_correct += 1

        ok = status_ok and icd_ok and flags_ok
        if ok:
            passed += 1
        else:
            failed.append(
                {
                    "index": idx,
                    "input": tc.input,
                    "expected": {
                        "status": tc.expected_status,
                        "icd": tc.expected_icd,
                        "flags": tc.expected_flags,
                    },
                    "actual": {
                        "status": actual_status,
                        "icd_prefixes": prefixes,
                        "flags": actual_flags,
                        "confidence": trace.get("confidence"),
                    },
                    "trace": trace,
                }
            )

        if args.verbose or not ok:
            clinical = trace.get("clinical") or {}
            coding = trace.get("coding") or {}
            payer = trace.get("payer") or {}
            print(f"\n=== CASE {idx} ===")
            print(f"INPUT: {tc.input}")
            print(f"EXPECTED: status={tc.expected_status}, icd={tc.expected_icd}, flags={tc.expected_flags}")
            print(f"ACTUAL:   status={actual_status}, icd_prefixes={prefixes}, flags={actual_flags}, confidence={trace.get('confidence')}")
            print("\n-- Clinical Agent --")
            print(json.dumps(clinical, indent=2))
            print("\n-- Coding Agent --")
            coding_preview = dict(coding)
            if isinstance(coding_preview.get("icd_codes"), list):
                coding_preview["icd_codes"] = coding_preview["icd_codes"][:10]
            print(json.dumps(coding_preview, indent=2))
            print("\n-- Rule Agent --")
            print(json.dumps(payer, indent=2))

    accuracy = (icd_correct / icd_cases * 100.0) if icd_cases else 0.0
    edge_rate = (edge_correct / edge_expected * 100.0) if edge_expected else 0.0

    report = {
        "total": total,
        "passed": passed,
        "failed": len(failed),
        "accuracy_icd_percent": accuracy,
        "edge_flag_coverage_percent": edge_rate,
        "failed_cases": [
            {
                "index": f["index"],
                "input": f["input"],
                "expected": f["expected"],
                "actual": f["actual"],
            }
            for f in failed
        ],
    }

    print("\n===== TEST REPORT =====")
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(failed)}")
    print(f"Accuracy: {accuracy:.2f}%")
    print(f"% Correctly Flagged Edge Cases: {edge_rate:.2f}%")

    if failed:
        print("\n===== FAILED CASES =====")
        for f in failed:
            print(f"\n--- Case {f['index']} ---")
            print(f"Input: {f['input']}")
            print("Expected:", json.dumps(f["expected"], indent=2))
            print("Actual:", json.dumps(f["actual"], indent=2))

    if args.save_json:
        out_path = _tmp_dir() / "test_report.json"
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nSaved report: {out_path.as_posix()}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
