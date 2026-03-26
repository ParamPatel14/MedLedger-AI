import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, TypedDict


logger = logging.getLogger("app.utils.terminology")


class TerminologyPayload(TypedDict):
    diagnosis_abbrev: Dict[str, str]
    medication_abbrev: Dict[str, str]
    procedure_abbrev: Dict[str, str]
    diagnosis_terms: List[str]
    medication_terms: List[str]


@dataclass
class TerminologyStore:
    path: Path
    mtime_ns: int
    payload: TerminologyPayload


def _default_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "terminology.json"


def load_terminology_store(previous: Optional[TerminologyStore] = None) -> TerminologyStore:
    path = Path(os.getenv("TERMINOLOGY_JSON") or _default_path())
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        return TerminologyStore(
            path=path,
            mtime_ns=0,
            payload={
                "diagnosis_abbrev": {},
                "medication_abbrev": {},
                "procedure_abbrev": {},
                "diagnosis_terms": [],
                "medication_terms": [],
            },
        )

    if previous and previous.path == path and previous.mtime_ns == mtime_ns:
        return previous

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        payload: TerminologyPayload = {
            "diagnosis_abbrev": {str(k).lower(): str(v).lower() for k, v in (data.get("diagnosis_abbrev") or {}).items()},
            "medication_abbrev": {str(k).lower(): str(v).lower() for k, v in (data.get("medication_abbrev") or {}).items()},
            "procedure_abbrev": {str(k).lower(): str(v).lower() for k, v in (data.get("procedure_abbrev") or {}).items()},
            "diagnosis_terms": [str(x).lower() for x in (data.get("diagnosis_terms") or []) if str(x).strip()],
            "medication_terms": [str(x).lower() for x in (data.get("medication_terms") or []) if str(x).strip()],
        }
        return TerminologyStore(path=path, mtime_ns=mtime_ns, payload=payload)
    except Exception:
        logger.exception("Failed to load terminology JSON")
        return TerminologyStore(
            path=path,
            mtime_ns=mtime_ns,
            payload={
                "diagnosis_abbrev": {},
                "medication_abbrev": {},
                "procedure_abbrev": {},
                "diagnosis_terms": [],
                "medication_terms": [],
            },
        )
