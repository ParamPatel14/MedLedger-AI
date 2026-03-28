from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.layers.svm_layer.selectors import select_all


def _as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def _apply_transforms(value: Any, transforms: Sequence[str]) -> Any:
    v = value
    for t in transforms:
        k = str(t or "").strip().lower()
        if not k:
            continue
        if isinstance(v, str):
            if k == "strip":
                v = v.strip()
                continue
            if k == "lower":
                v = v.lower()
                continue
            if k == "upper":
                v = v.upper()
                continue
        if k == "string":
            v = _as_str(v)
            continue
    return v


def get_values(obj: Any, path: str, *, transforms: Optional[Sequence[str]] = None) -> List[Any]:
    vals = select_all(obj, path)
    if transforms:
        return [_apply_transforms(v, transforms) for v in vals]
    return vals


def first_value(obj: Any, path: str, *, transforms: Optional[Sequence[str]] = None) -> Any:
    vals = get_values(obj, path, transforms=transforms)
    return vals[0] if vals else None


def _issue_severities(issues: List[dict]) -> List[str]:
    out: List[str] = []
    for it in issues:
        if not isinstance(it, dict):
            continue
        out.append(str(it.get("severity") or "").lower())
    return out


def _issue_types(issues: List[dict]) -> List[str]:
    out: List[str] = []
    for it in issues:
        if not isinstance(it, dict):
            continue
        out.append(str(it.get("type") or "").strip())
    return out


@dataclass(frozen=True)
class DecisionInputs:
    raw_text: str
    workflow_confidence: float
    svm: Dict[str, Any]
    policy_issues: List[dict]
    edge_issues: List[dict]
    external_issues: List[dict]

    @property
    def all_issues(self) -> List[dict]:
        return [*self.policy_issues, *self.edge_issues, *self.external_issues]


def evaluate_condition(cond: Dict[str, Any], *, ctx: Dict[str, Any], decision_inputs: DecisionInputs) -> bool:
    kind = str(cond.get("kind") or "").strip()
    if kind == "always":
        return True
    if kind == "raw_text_empty":
        return not bool((decision_inputs.raw_text or "").strip())
    if kind == "issue_severity_in":
        values = {str(x).lower() for x in _as_list(cond.get("values"))}
        severities = set(_issue_severities(decision_inputs.all_issues))
        return bool(values.intersection(severities))
    if kind == "issue_type_in":
        values = {str(x) for x in _as_list(cond.get("values"))}
        types = set(_issue_types(decision_inputs.all_issues))
        return bool(values.intersection(types))
    if kind == "confidence_lt":
        thr_key = str(cond.get("threshold_key") or "").strip()
        thresholds = (ctx.get("thresholds") or {}).get("thresholds") or {}
        try:
            thr = float(thresholds.get(thr_key))
        except Exception:
            thr = None
        if thr is None:
            return False
        return float(decision_inputs.workflow_confidence or 0.0) < thr
    if kind == "path_len_gte":
        path = str(cond.get("path") or "").strip()
        try:
            n = int(cond.get("value"))
        except Exception:
            n = 0
        return len(get_values(ctx, path)) >= n
    if kind == "path_len_lte":
        path = str(cond.get("path") or "").strip()
        try:
            n = int(cond.get("value"))
        except Exception:
            n = 0
        return len(get_values(ctx, path)) <= n
    if kind == "path_any_equals":
        path = str(cond.get("path") or "").strip()
        target = cond.get("value")
        vals = get_values(ctx, path)
        return any(v == target for v in vals)
    if kind in {"path_number_gt", "path_number_gte", "path_number_lt", "path_number_lte"}:
        path = str(cond.get("path") or "").strip()
        try:
            target = float(cond.get("value"))
        except Exception:
            return False
        vals = get_values(ctx, path)
        nums: List[float] = []
        for v in vals:
            try:
                nums.append(float(v))
            except Exception:
                continue
        if not nums:
            return False
        if kind == "path_number_gt":
            return any(n > target for n in nums)
        if kind == "path_number_gte":
            return any(n >= target for n in nums)
        if kind == "path_number_lt":
            return any(n < target for n in nums)
        return any(n <= target for n in nums)
    if kind == "svm_status_in":
        values = {str(x).lower() for x in _as_list(cond.get("values"))}
        statuses: List[str] = []
        if isinstance(decision_inputs.svm, dict):
            for v in decision_inputs.svm.values():
                if isinstance(v, dict):
                    statuses.append(str(v.get("status") or "").lower())
        return bool(values.intersection(set(statuses)))
    if kind == "all":
        rules = cond.get("rules") or []
        if not isinstance(rules, list):
            return False
        return all(evaluate_condition(r, ctx=ctx, decision_inputs=decision_inputs) for r in rules if isinstance(r, dict))
    if kind == "any":
        rules = cond.get("rules") or []
        if not isinstance(rules, list):
            return False
        return any(evaluate_condition(r, ctx=ctx, decision_inputs=decision_inputs) for r in rules if isinstance(r, dict))
    if kind == "regex_match":
        path = str(cond.get("path") or "").strip()
        pattern = str(cond.get("pattern") or "")
        vals = get_values(ctx, path, transforms=["string"])
        try:
            rx = re.compile(pattern, flags=re.IGNORECASE)
        except Exception:
            return False
        return any(bool(rx.search(_as_str(v))) for v in vals)
    return False
