from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.layers.governance_layer.evaluation import _as_list, _as_str, get_values


def _uniq_preserve(items: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _normalize_strings(values: List[Any], transforms: Sequence[str]) -> List[str]:
    out: List[str] = []
    for v in values:
        s = _as_str(v)
        for t in transforms:
            k = str(t or "").strip().lower()
            if not k:
                continue
            if k == "strip":
                s = s.strip()
            elif k == "lower":
                s = s.lower()
            elif k == "upper":
                s = s.upper()
        if s:
            out.append(s)
    return out


@dataclass(frozen=True)
class PolicyResult:
    issues: List[dict]


class PolicyEngine:
    def evaluate(self, *, ctx: Dict[str, Any], policies_cfg: Dict[str, Any]) -> PolicyResult:
        policies = policies_cfg.get("policies") or []
        if not isinstance(policies, list):
            policies = []

        issues: List[dict] = []
        for p in policies:
            if not isinstance(p, dict):
                continue
            rule = p.get("rule") or {}
            if not isinstance(rule, dict):
                continue
            kind = str(rule.get("kind") or "").strip()
            if not kind:
                continue
            ok, details = self._eval_rule(kind=kind, rule=rule, ctx=ctx)
            if ok:
                continue
            issues.append(
                {
                    "type": str(p.get("type") or "policy"),
                    "severity": str(p.get("severity") or "warning").lower(),
                    "message": str(p.get("message") or "Policy violation"),
                    "policy_id": str(p.get("id") or ""),
                    "details": details or {},
                }
            )
        return PolicyResult(issues=issues)

    def _eval_rule(self, *, kind: str, rule: Dict[str, Any], ctx: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        if kind == "required_non_empty":
            paths = rule.get("paths") or []
            if not isinstance(paths, list):
                paths = []
            missing: List[str] = []
            for p in paths:
                path = str(p or "").strip()
                if not path:
                    continue
                vals = get_values(ctx, path)
                if not vals:
                    missing.append(path)
                    continue
                if all((v is None) or (_as_str(v).strip() == "") for v in vals):
                    missing.append(path)
            return (not missing), {"missing_paths": missing}

        if kind == "no_duplicates":
            path = str(rule.get("path") or "").strip()
            transforms = rule.get("transforms") or []
            if not isinstance(transforms, list):
                transforms = []
            vals = get_values(ctx, path)
            strings = _normalize_strings(vals, transforms)
            dups: List[str] = []
            seen: set[str] = set()
            for s in strings:
                if s in seen and s not in dups:
                    dups.append(s)
                seen.add(s)
            return (not dups), {"duplicates": dups}

        if kind == "source_text_supports_items":
            raw_text = _as_str(ctx.get("raw_text") or "")
            items_path = str(rule.get("items_path") or "").strip()
            match_method = str(rule.get("match_method") or "substring_ci").strip().lower()
            try:
                min_supported_ratio = float(rule.get("min_supported_ratio") if rule.get("min_supported_ratio") is not None else 1.0)
            except Exception:
                min_supported_ratio = 1.0
            try:
                min_items = int(rule.get("min_items") if rule.get("min_items") is not None else 1)
            except Exception:
                min_items = 1
            items = [x for x in _normalize_strings(get_values(ctx, items_path), ["strip"]) if x]
            if len(items) < min_items:
                return False, {"supported_ratio": 0.0, "items": items, "supported": []}
            raw = raw_text.lower()
            supported: List[str] = []
            for it in items:
                it_s = it.strip()
                if not it_s:
                    continue
                if match_method == "regex":
                    try:
                        if re.search(it_s, raw_text, flags=re.IGNORECASE):
                            supported.append(it_s)
                    except Exception:
                        continue
                else:
                    if it_s.lower() in raw:
                        supported.append(it_s)
            supported = _uniq_preserve(supported)
            ratio = (len(supported) / len(items)) if items else 1.0
            return (ratio >= min_supported_ratio), {"supported_ratio": ratio, "items": items, "supported": supported}

        if kind == "procedure_requires_any_diagnosis":
            procs_path = str(rule.get("procedures_path") or "").strip()
            dx_path = str(rule.get("diagnoses_path") or "").strip()
            links = rule.get("links") or []
            if not isinstance(links, list):
                links = []
            procedures = _normalize_strings(get_values(ctx, procs_path), ["strip", "lower"])
            diagnoses = _normalize_strings(get_values(ctx, dx_path), ["strip", "lower"])
            missing: List[dict] = []
            for link in links:
                if not isinstance(link, dict):
                    continue
                proc_rx = str(link.get("procedure_regex") or "").strip()
                req_arr = link.get("requires_diagnosis_regex") or []
                if not isinstance(req_arr, list):
                    req_arr = []
                if not proc_rx or not req_arr:
                    continue
                try:
                    pr = re.compile(proc_rx, flags=re.IGNORECASE)
                except Exception:
                    continue
                req_res: List[re.Pattern[str]] = []
                for r in req_arr:
                    try:
                        req_res.append(re.compile(str(r or ""), flags=re.IGNORECASE))
                    except Exception:
                        continue
                matched_procs = [p for p in procedures if pr.search(p)]
                if not matched_procs:
                    continue
                ok = False
                for d in diagnoses:
                    if any(rx.search(d) for rx in req_res):
                        ok = True
                        break
                if not ok:
                    missing.append({"procedure_regex": proc_rx, "procedures": matched_procs})
            return (not missing), {"missing_links": missing}

        return True, {}

