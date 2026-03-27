from __future__ import annotations

import re
from typing import Any, Iterable, List, Sequence, Tuple


_TOKEN_RE = re.compile(r"^([a-zA-Z0-9_-]+)(\[(\*|\d+)\])?$")


def _iter_items(value: Any) -> Iterable[Tuple[str, Any]]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k), v
        return
    if isinstance(value, list):
        for i, v in enumerate(value):
            yield str(i), v
        return


def select_all(obj: Any, path: str) -> List[Any]:
    p = (path or "").strip()
    if not p:
        return []

    parts = [x for x in p.split(".") if x]
    current: List[Any] = [obj]
    for part in parts:
        m = _TOKEN_RE.match(part)
        if not m:
            return []
        key = m.group(1)
        idx = m.group(3)

        next_items: List[Any] = []
        for item in current:
            if not isinstance(item, (dict, list)):
                continue
            if isinstance(item, dict):
                if key not in item:
                    continue
                target = item.get(key)
            else:
                try:
                    target = item[int(key)]
                except Exception:
                    continue

            if idx is None:
                next_items.append(target)
            elif idx == "*":
                if isinstance(target, list):
                    next_items.extend(list(target))
                elif isinstance(target, dict):
                    next_items.extend([v for _, v in _iter_items(target)])
            else:
                try:
                    n = int(idx)
                except Exception:
                    continue
                if isinstance(target, list) and 0 <= n < len(target):
                    next_items.append(target[n])
                elif isinstance(target, dict):
                    val = target.get(str(n))
                    if val is not None:
                        next_items.append(val)

        current = next_items
        if not current:
            return []

    out: List[Any] = []
    for item in current:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


def flatten_primitives(obj: Any, *, max_depth: int) -> List[dict]:
    out: List[dict] = []

    def walk(node: Any, path: Sequence[str], depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, [*path, str(k)], depth + 1)
            return
        if isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, [*path, f"[{i}]"], depth + 1)
            return
        if node is None:
            return
        if isinstance(node, (str, int, float, bool)):
            out.append({"path": ".".join(path), "value": node})

    walk(obj, [], 0)
    return out
