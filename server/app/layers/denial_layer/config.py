from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class DenialConfigStore:
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


def _read_config(path: Path) -> DenialConfigStore:
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        raise RuntimeError(f"Denial config not found: {path.as_posix()}")
    raw = path.read_text(encoding="utf-8")
    try:
        cfg = _load_config_text(path, raw)
    except Exception as e:
        raise RuntimeError(f"Failed to parse denial config: {path.as_posix()} ({e})") from e
    return DenialConfigStore(path=path, mtime_ns=mtime_ns, config=cfg)


def _default_path(env_key: str, filename: str) -> Path:
    configured = (os.getenv(env_key) or "").strip()
    if configured:
        return Path(configured)
    return Path.cwd() / "app" / "config" / filename


_MAPPINGS_CACHE: Optional[DenialConfigStore] = None
_THRESHOLDS_CACHE: Optional[DenialConfigStore] = None
_RULES_CACHE: Optional[DenialConfigStore] = None


def _load_cached(path: Path, previous: Optional[DenialConfigStore]) -> Tuple[DenialConfigStore, Dict[str, Any]]:
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        raise RuntimeError(f"Denial config not found: {path.as_posix()}")

    if previous and previous.path == path and previous.mtime_ns == mtime_ns:
        return previous, previous.config
    store = _read_config(path)
    return store, store.config


def get_denial_mappings() -> Dict[str, Any]:
    global _MAPPINGS_CACHE
    path = _default_path("DENIAL_MAPPINGS_PATH", "denial_mappings.json")
    store, cfg = _load_cached(path, _MAPPINGS_CACHE)
    _MAPPINGS_CACHE = store
    return cfg


def get_denial_thresholds() -> Dict[str, Any]:
    global _THRESHOLDS_CACHE
    path = _default_path("DENIAL_THRESHOLDS_PATH", "denial_thresholds.json")
    store, cfg = _load_cached(path, _THRESHOLDS_CACHE)
    _THRESHOLDS_CACHE = store
    return cfg


def get_denial_rules() -> Dict[str, Any]:
    global _RULES_CACHE
    path = _default_path("DENIAL_RULES_PATH", "denial_rules.json")
    store, cfg = _load_cached(path, _RULES_CACHE)
    _RULES_CACHE = store
    return cfg

