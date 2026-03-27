from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.layers.coding_layer.services.embedding_service import encode_text, normalize_single
from app.layers.svm_layer.claim_extractor import Claim
from app.layers.svm_layer.selectors import select_all


@dataclass(frozen=True)
class VerificationResult:
    score: float
    issues: List[dict]
    explanations: List[str]


def _clamp01(x: float) -> float:
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return float(x)


def _as_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v)


class SourceAlignmentVerifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config

    def verify(self, *, raw_text: str, claims: List[Claim]) -> VerificationResult:
        cfg = (self._cfg.get("verification") or {}).get("source_alignment") or {}
        if not bool(cfg.get("enabled", True)):
            return VerificationResult(score=1.0, issues=[], explanations=["source_alignment disabled"])

        raw = (raw_text or "").strip()
        if not raw:
            return VerificationResult(score=0.0, issues=[{"type": "missing_input", "severity": "critical", "message": "Missing raw input text"}], explanations=["Missing raw input text"])

        raw_vec = encode_text(raw)
        if raw_vec is None:
            return VerificationResult(score=0.0, issues=[{"type": "embedding_unavailable", "severity": "critical", "message": "Embedding model unavailable for source alignment"}], explanations=["Embedding model unavailable"])
        raw_vec = normalize_single(np.asarray(raw_vec, dtype=np.float32))

        type_cfg = cfg.get("claim_types") or {}
        if not isinstance(type_cfg, dict):
            type_cfg = {}
        only_configured = bool(cfg.get("only_configured_types", False))

        per_scores: List[float] = []
        issues: List[dict] = []
        explanations: List[str] = []

        for c in claims:
            t = str(c.type or "").strip()
            if only_configured and t not in type_cfg:
                continue
            tc = type_cfg.get(t) or {}
            if not isinstance(tc, dict):
                tc = {}
            if tc.get("enabled") is False:
                continue
            method = str(tc.get("method") or cfg.get("default_method") or "semantic_cosine").strip()
            try:
                min_sim = float(tc.get("min_similarity") if tc.get("min_similarity") is not None else cfg.get("min_similarity"))
            except Exception:
                min_sim = 0.0

            text = _as_text(c.value)
            if not text:
                continue

            if method == "substring":
                ok = text.lower() in raw.lower()
                s = 1.0 if ok else 0.0
            elif method == "regex":
                pat = str(tc.get("pattern") or "").strip()
                if not pat:
                    s = 0.0
                else:
                    s = 1.0 if re.search(pat, raw, flags=re.IGNORECASE) else 0.0
            else:
                vec = encode_text(text)
                if vec is None:
                    s = 0.0
                else:
                    vec = normalize_single(np.asarray(vec, dtype=np.float32))
                    s = float(np.dot(raw_vec, vec))
                    s = _clamp01(s)

            per_scores.append(s)
            explanations.append(f"source_alignment:{t}={s:.3f}")
            if s < min_sim:
                issues.append(
                    {
                        "type": "hallucinated_claim",
                        "severity": str(tc.get("severity") or cfg.get("severity") or "warning").lower(),
                        "claim_type": t,
                        "claim_path": c.path,
                        "message": str(tc.get("message") or cfg.get("message") or "Claim is weakly supported by source text"),
                        "score": s,
                    }
                )

        score = sum(per_scores) / len(per_scores) if per_scores else 1.0
        return VerificationResult(score=_clamp01(score), issues=issues, explanations=explanations)


def _match_pattern(value: str, pattern: Dict[str, Any]) -> bool:
    mode = str(pattern.get("mode") or "equals").strip().lower()
    target = pattern.get("value")
    if mode == "equals":
        return value == str(target or "")
    if mode == "in":
        arr = pattern.get("values") or []
        if not isinstance(arr, list):
            return False
        return value in {str(x or "") for x in arr}
    if mode == "prefix":
        return value.startswith(str(target or ""))
    if mode == "regex":
        try:
            return re.search(str(target or ""), value, flags=re.IGNORECASE) is not None
        except Exception:
            return False
    return False


class InterAgentConsistencyVerifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config

    def verify(self, *, current_claims: List[Claim], prior_claims: List[Claim]) -> VerificationResult:
        cfg = (self._cfg.get("verification") or {}).get("inter_agent_consistency") or {}
        if not bool(cfg.get("enabled", True)):
            return VerificationResult(score=1.0, issues=[], explanations=["consistency disabled"])

        rules = cfg.get("rules") or []
        if not isinstance(rules, list):
            rules = []

        issues: List[dict] = []
        explanations: List[str] = []

        def claims_by_type(claims: List[Claim], t: str) -> List[str]:
            out: List[str] = []
            for c in claims:
                if str(c.type) != t:
                    continue
                v = _as_text(c.value)
                if v:
                    out.append(v)
            return out

        combined = prior_claims + current_claims

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rtype = str(rule.get("type") or "").strip().lower()
            severity = str(rule.get("severity") or "warning").lower()
            message = str(rule.get("message") or "Consistency rule triggered")
            rid = str(rule.get("id") or rtype or "rule").strip()

            if rtype == "mutually_exclusive":
                claim_type = str(rule.get("claim_type") or "").strip()
                groups = rule.get("groups") or []
                if not claim_type or not isinstance(groups, list):
                    continue
                vals = claims_by_type(combined, claim_type)
                vset = {v.lower() for v in vals}
                for g in groups:
                    if not isinstance(g, list):
                        continue
                    items = [str(x or "").lower() for x in g if str(x or "").strip()]
                    matched = [x for x in items if x in vset]
                    if len(matched) > 1:
                        issues.append({"type": "contradicting_agents", "severity": severity, "rule_id": rid, "claim_type": claim_type, "values": matched, "message": message})
                        explanations.append(f"consistency:{rid}=triggered")
                        break
                continue

            if rtype == "requires":
                if_pat = rule.get("if") or {}
                then_pat = rule.get("then_requires") or {}
                if not isinstance(if_pat, dict) or not isinstance(then_pat, dict):
                    continue
                if_type = str(if_pat.get("claim_type") or "").strip()
                then_type = str(then_pat.get("claim_type") or "").strip()
                if not if_type or not then_type:
                    continue
                if_vals = claims_by_type(current_claims, if_type)
                if not if_vals:
                    continue
                then_vals = claims_by_type(combined, then_type)
                if not then_vals:
                    issues.append({"type": "missing_required_data", "severity": severity, "rule_id": rid, "message": message})
                    explanations.append(f"consistency:{rid}=missing")
                continue

            if rtype == "not_coexist":
                left = rule.get("left") or {}
                right = rule.get("right") or {}
                if not isinstance(left, dict) or not isinstance(right, dict):
                    continue
                lt = str(left.get("claim_type") or "").strip()
                rt = str(right.get("claim_type") or "").strip()
                if not lt or not rt:
                    continue
                lp = left.get("pattern") or {}
                rp = right.get("pattern") or {}
                if not isinstance(lp, dict) or not isinstance(rp, dict):
                    continue
                lvals = claims_by_type(combined, lt)
                rvals = claims_by_type(combined, rt)
                hit_l = any(_match_pattern(v, lp) for v in lvals)
                hit_r = any(_match_pattern(v, rp) for v in rvals)
                if hit_l and hit_r:
                    issues.append({"type": "contradicting_agents", "severity": severity, "rule_id": rid, "message": message})
                    explanations.append(f"consistency:{rid}=contradiction")
                continue

        sev_weights = cfg.get("severity_weights") or {}
        if not isinstance(sev_weights, dict):
            sev_weights = {}
        penalty = 0.0
        for it in issues:
            sev = str(it.get("severity") or "warning").lower()
            try:
                penalty += float(sev_weights.get(sev))
            except Exception:
                penalty += 0.0
        score = _clamp01(1.0 - penalty)
        return VerificationResult(score=score, issues=issues, explanations=explanations)


class ReasonabilityVerifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config

    def verify(self, *, agent_output: Dict[str, Any]) -> VerificationResult:
        cfg = (self._cfg.get("verification") or {}).get("reasonability") or {}
        if not bool(cfg.get("enabled", True)):
            return VerificationResult(score=1.0, issues=[], explanations=["reasonability disabled"])

        rules = cfg.get("rules") or []
        if not isinstance(rules, list):
            rules = []

        issues: List[dict] = []
        explanations: List[str] = []

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rtype = str(rule.get("type") or "").strip().lower()
            rid = str(rule.get("id") or rtype or "rule").strip()
            severity = str(rule.get("severity") or "warning").lower()
            message = str(rule.get("message") or "Reasonability rule triggered")

            if rtype == "numeric_range":
                path = str(rule.get("path") or "").strip()
                if not path:
                    continue
                values = select_all(agent_output, path)
                if not values:
                    continue
                try:
                    mn = float(rule.get("min"))
                except Exception:
                    mn = None
                try:
                    mx = float(rule.get("max"))
                except Exception:
                    mx = None
                for v in values:
                    try:
                        x = float(v)
                    except Exception:
                        issues.append({"type": "unrealistic_numeric", "severity": severity, "rule_id": rid, "path": path, "message": message})
                        continue
                    if mn is not None and x < mn:
                        issues.append({"type": "unrealistic_numeric", "severity": severity, "rule_id": rid, "path": path, "message": message})
                    if mx is not None and x > mx:
                        issues.append({"type": "unrealistic_numeric", "severity": severity, "rule_id": rid, "path": path, "message": message})
                explanations.append(f"reasonability:{rid}=checked")
                continue

            if rtype == "required_paths":
                paths = rule.get("paths") or []
                if not isinstance(paths, list):
                    continue
                for p in paths:
                    sp = str(p or "").strip()
                    if not sp:
                        continue
                    vals = select_all(agent_output, sp)
                    if not vals:
                        issues.append({"type": "missing_required_data", "severity": severity, "rule_id": rid, "path": sp, "message": message})
                explanations.append(f"reasonability:{rid}=checked")
                continue

        sev_weights = cfg.get("severity_weights") or {}
        if not isinstance(sev_weights, dict):
            sev_weights = {}
        penalty = 0.0
        for it in issues:
            sev = str(it.get("severity") or "warning").lower()
            try:
                penalty += float(sev_weights.get(sev))
            except Exception:
                penalty += 0.0
        score = _clamp01(1.0 - penalty)
        return VerificationResult(score=score, issues=issues, explanations=explanations)
