from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class JsonPatchOp:
    op: str
    path: str
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"op": self.op, "path": self.path}
        if self.op in {"add", "replace"}:
            out["value"] = self.value
        return out


def deep_copy(obj: Any) -> Any:
    try:
        return copy.deepcopy(obj)
    except Exception:
        return obj


def _split_path(path: str) -> List[str]:
    return [p for p in str(path or "").strip().split(".") if p]


def _navigate(root: Any, parts: List[str], *, create: bool) -> Tuple[Any, Optional[str]]:
    cur = root
    if not parts:
        return cur, None
    for key in parts[:-1]:
        if isinstance(cur, dict):
            if key not in cur or cur[key] is None:
                if not create:
                    return None, None
                cur[key] = {}
            cur = cur[key]
            continue
        return None, None
    return cur, parts[-1]


def get_path(root: Any, path: str) -> Any:
    parts = _split_path(path)
    cur = root
    for key in parts:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
            continue
        return None
    return cur


def set_path(root: Any, path: str, value: Any) -> List[JsonPatchOp]:
    parts = _split_path(path)
    parent, leaf = _navigate(root, parts, create=True)
    if parent is None or leaf is None or not isinstance(parent, dict):
        return []
    existed = leaf in parent
    parent[leaf] = value
    return [JsonPatchOp(op="replace" if existed else "add", path=path, value=value)]


def delete_path(root: Any, path: str) -> List[JsonPatchOp]:
    parts = _split_path(path)
    parent, leaf = _navigate(root, parts, create=False)
    if parent is None or leaf is None or not isinstance(parent, dict):
        return []
    if leaf not in parent:
        return []
    del parent[leaf]
    return [JsonPatchOp(op="remove", path=path)]


def append_path(root: Any, path: str, value: Any) -> List[JsonPatchOp]:
    existing = get_path(root, path)
    if existing is None:
        ops = set_path(root, path, [value])
        return ops
    if not isinstance(existing, list):
        return []
    existing.append(value)
    return [JsonPatchOp(op="add", path=f"{path}[]", value=value)]


def filter_list_in_place(root: Any, path: str, keep_mask: List[bool]) -> List[JsonPatchOp]:
    existing = get_path(root, path)
    if not isinstance(existing, list):
        return []
    if len(existing) != len(keep_mask):
        return []
    new_list = [v for v, keep in zip(existing, keep_mask) if keep]
    return set_path(root, path, new_list)


def detect_patch_conflicts(patches: List[JsonPatchOp], conflict_fields: List[str]) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    by_path: Dict[str, List[JsonPatchOp]] = {}
    for op in patches:
        by_path.setdefault(op.path, []).append(op)

    for path, ops in by_path.items():
        if len(ops) <= 1:
            continue
        if conflict_fields and path not in set(conflict_fields):
            continue
        values = []
        for it in ops:
            if it.op in {"add", "replace"}:
                values.append(it.value)
        distinct = {repr(v) for v in values}
        if len(distinct) > 1:
            conflicts.append(
                {
                    "type": "conflicting_fixes",
                    "severity": "critical",
                    "path": path,
                    "values": values,
                }
            )
    return conflicts

