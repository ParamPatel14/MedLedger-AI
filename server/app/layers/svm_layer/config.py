from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class SvmConfigStore:
    path: Path
    mtime_ns: int
    config: Dict[str, Any]


def _default_path() -> Path:
    configured = (os.getenv("SVM_CONFIG_PATH") or "").strip()
    if configured:
        return Path(configured)
    return Path.cwd() / "app" / "config" / "svm_config.json"


_CACHE: Optional[SvmConfigStore] = None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def load_svm_config(previous: Optional[SvmConfigStore] = None) -> Tuple[SvmConfigStore, Dict[str, Any]]:
    path = _default_path()
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
    except Exception:
        raise RuntimeError(f"SVM config not found: {path.as_posix()}")

    if previous and previous.path == path and previous.mtime_ns == mtime_ns:
        return previous, previous.config

    raw = _read_text(path)
    try:
        cfg = _load_config_text(path, raw)
    except Exception as e:
        raise RuntimeError(f"Failed to parse SVM config: {path.as_posix()} ({e})") from e

    store = SvmConfigStore(path=path, mtime_ns=mtime_ns, config=cfg)
    return store, cfg


def get_svm_config() -> Dict[str, Any]:
    global _CACHE
    store, cfg = load_svm_config(_CACHE)
    _CACHE = store
    return cfg

