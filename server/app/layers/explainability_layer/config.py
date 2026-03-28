from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ExplainabilityConfigStore:
    path: Path
    mtime_ns: int
    config: Dict[str, Any]


def _load_yaml(text: str) -> Dict[str, Any]:
    import yaml

    data = yaml.safe_load(text) if text.strip() else {}
    return data if isinstance(data, dict) else {}


def _load_config_text(path: Path, text: str) -> Dict[str, Any]:
    ext = path.suffix.lower().lstrip(".")
    if ext in {"yaml", "yml"}:
        return _load_yaml(text)
    data = json.loads(text) if text.strip() else {}
    return data if isinstance(data, dict) else {}


def _default_path(env_key: str, filename: str) -> Path:
    configured = (os.getenv(env_key) or "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "config" / filename


def _load_cached(path: Path, previous: Optional[ExplainabilityConfigStore]) -> Tuple[ExplainabilityConfigStore, Dict[str, Any]]:
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        raise RuntimeError(f"Explainability config not found: {path.as_posix()}")

    if previous and previous.path == path and previous.mtime_ns == mtime_ns:
        return previous, previous.config

    raw = path.read_text(encoding="utf-8")
    try:
        cfg = _load_config_text(path, raw)
    except Exception as e:
        raise RuntimeError(f"Failed to parse explainability config: {path.as_posix()} ({e})") from e

    store = ExplainabilityConfigStore(path=path, mtime_ns=mtime_ns, config=cfg)
    return store, cfg


_TEMPLATES_CACHE: Optional[ExplainabilityConfigStore] = None
_RULES_CACHE: Optional[ExplainabilityConfigStore] = None


def get_explainability_templates() -> Dict[str, Any]:
    global _TEMPLATES_CACHE
    path = _default_path("EXPLAIN_TEMPLATES_PATH", "explainability_templates.json")
    store, cfg = _load_cached(path, _TEMPLATES_CACHE)
    _TEMPLATES_CACHE = store
    return cfg


def get_explainability_rules() -> Dict[str, Any]:
    global _RULES_CACHE
    path = _default_path("EXPLAIN_RULES_PATH", "explainability_rules.json")
    store, cfg = _load_cached(path, _RULES_CACHE)
    _RULES_CACHE = store
    return cfg
