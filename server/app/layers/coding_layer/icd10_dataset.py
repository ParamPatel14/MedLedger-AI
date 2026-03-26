from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


@dataclass(frozen=True)
class IcdRow:
    code: str
    description: str


def _datasets_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "datasets"


def icd10_path() -> Path:
    return _datasets_dir() / "ICD10codes.csv"


def compute_dataset_version(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def load_icd10_rows(path: Path) -> Tuple[str, List[IcdRow]]:
    version = compute_dataset_version(path)
    rows: List[IcdRow] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        for parts in reader:
            if not parts:
                continue
            if len(parts) < 4:
                continue
            code = str(parts[2]).strip()
            desc = str(parts[3]).strip()
            if not code or not desc:
                continue
            rows.append(IcdRow(code=code, description=desc))
    return version, rows


def iter_descriptions(rows: Iterable[IcdRow]) -> List[str]:
    return [r.description for r in rows]
