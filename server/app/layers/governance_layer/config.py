from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class GovernanceConfigStore:
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


def _read_config(path: Path) -> GovernanceConfigStore:
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        raise RuntimeError(f"Governance config not found: {path.as_posix()}")
    raw = path.read_text(encoding="utf-8")
    try:
        cfg = _load_config_text(path, raw)
    except Exception as e:
        raise RuntimeError(f"Failed to parse governance config: {path.as_posix()} ({e})") from e
    return GovernanceConfigStore(path=path, mtime_ns=mtime_ns, config=cfg)


def _default_path(env_key: str, filename: str) -> Path:
    configured = (os.getenv(env_key) or "").strip()
    if configured:
        return Path(configured)
    return Path.cwd() / "app" / "config" / filename


_POLICIES_CACHE: Optional[GovernanceConfigStore] = None
_THRESHOLDS_CACHE: Optional[GovernanceConfigStore] = None
_RULES_CACHE: Optional[GovernanceConfigStore] = None


def _load_cached(path: Path, previous: Optional[GovernanceConfigStore]) -> Tuple[GovernanceConfigStore, Dict[str, Any]]:
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        raise RuntimeError(f"Governance config not found: {path.as_posix()}")

    if previous and previous.path == path and previous.mtime_ns == mtime_ns:
        return previous, previous.config
    store = _read_config(path)
    return store, store.config


def get_governance_policies() -> Dict[str, Any]:
    global _POLICIES_CACHE
    path = _default_path("GOVERNANCE_POLICIES_PATH", "policies.json")
    store, cfg = _load_cached(path, _POLICIES_CACHE)
    _POLICIES_CACHE = store
    return cfg


def get_governance_thresholds() -> Dict[str, Any]:
    global _THRESHOLDS_CACHE
    path = _default_path("GOVERNANCE_THRESHOLDS_PATH", "thresholds.json")
    store, cfg = _load_cached(path, _THRESHOLDS_CACHE)
    _THRESHOLDS_CACHE = store
    return cfg


def get_governance_rules() -> Dict[str, Any]:
    global _RULES_CACHE
    path = _default_path("GOVERNANCE_RULES_PATH", "rules.json")
    store, cfg = _load_cached(path, _RULES_CACHE)
    _RULES_CACHE = store
    return cfg

