from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class RuleIntelConfigStore:
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


def _read_config(path: Path) -> RuleIntelConfigStore:
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        raise RuntimeError(f"Rule config not found: {path.as_posix()}")
    raw = path.read_text(encoding="utf-8")
    try:
        cfg = _load_config_text(path, raw)
    except Exception as e:
        raise RuntimeError(f"Failed to parse rule config: {path.as_posix()} ({e})") from e
    return RuleIntelConfigStore(path=path, mtime_ns=mtime_ns, config=cfg)


def _default_path(env_key: str, filename: str) -> Path:
    configured = (os.getenv(env_key) or "").strip()
    if configured:
        return Path(configured)
    return Path.cwd() / "app" / "config" / filename


_EXTRACTION_CACHE: Optional[RuleIntelConfigStore] = None
_NORMALIZATION_CACHE: Optional[RuleIntelConfigStore] = None
_CONFIDENCE_CACHE: Optional[RuleIntelConfigStore] = None
_SCHEDULER_CACHE: Optional[RuleIntelConfigStore] = None


def _load_cached(path: Path, previous: Optional[RuleIntelConfigStore]) -> Tuple[RuleIntelConfigStore, Dict[str, Any]]:
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        raise RuntimeError(f"Rule config not found: {path.as_posix()}")

    if previous and previous.path == path and previous.mtime_ns == mtime_ns:
        return previous, previous.config
    store = _read_config(path)
    return store, store.config


def get_rule_extraction_config() -> Dict[str, Any]:
    global _EXTRACTION_CACHE
    path = _default_path("RULE_EXTRACTION_PATH", "rule_extraction_patterns.json")
    store, cfg = _load_cached(path, _EXTRACTION_CACHE)
    _EXTRACTION_CACHE = store
    return cfg


def get_rule_normalization_config() -> Dict[str, Any]:
    global _NORMALIZATION_CACHE
    path = _default_path("RULE_NORMALIZATION_PATH", "rule_normalization.json")
    store, cfg = _load_cached(path, _NORMALIZATION_CACHE)
    _NORMALIZATION_CACHE = store
    return cfg


def get_rule_confidence_config() -> Dict[str, Any]:
    global _CONFIDENCE_CACHE
    path = _default_path("RULE_CONFIDENCE_PATH", "rule_confidence.json")
    store, cfg = _load_cached(path, _CONFIDENCE_CACHE)
    _CONFIDENCE_CACHE = store
    return cfg


def get_rule_scheduler_config() -> Dict[str, Any]:
    global _SCHEDULER_CACHE
    path = _default_path("RULE_SCHEDULER_PATH", "rule_scheduler.json")
    store, cfg = _load_cached(path, _SCHEDULER_CACHE)
    _SCHEDULER_CACHE = store
    return cfg
