from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.layers.svm_layer.selectors import flatten_primitives, select_all


@dataclass(frozen=True)
class Claim:
    type: str
    value: Any
    source_agent: str
    path: str

    def to_dict(self) -> dict:
        return {"type": self.type, "value": self.value, "source_agent": self.source_agent, "path": self.path}


def _apply_transforms(value: Any, transforms: List[str]) -> Any:
    v = value
    for t in transforms:
        op = str(t or "").strip().lower()
        if not op:
            continue
        if op == "strip" and isinstance(v, str):
            v = v.strip()
        elif op == "lower" and isinstance(v, str):
            v = v.lower()
        elif op == "upper" and isinstance(v, str):
            v = v.upper()
        elif op == "to_string":
            v = str(v)
        elif op == "to_number":
            try:
                v = float(v)
            except Exception:
                v = v
    return v


class ClaimExtractionEngine:
    def __init__(self, config: Dict[str, Any]) -> None:
        self._cfg = config

    def extract(self, *, agent_name: str, agent_output: Dict[str, Any]) -> tuple[list[Claim], list[dict]]:
        cfg = self._cfg.get("claim_extraction") or {}
        agents = cfg.get("agents") or {}
        agent_cfg = agents.get(agent_name) or {}
        extractors = agent_cfg.get("extractors") or []
        issues: List[dict] = []
        claims: List[Claim] = []

        if isinstance(extractors, list) and extractors:
            for ex in extractors:
                if not isinstance(ex, dict):
                    continue
                claim_type = str(ex.get("type") or "").strip()
                path = str(ex.get("path") or "").strip()
                required = bool(ex.get("required", False))
                transforms = [str(x) for x in (ex.get("transforms") or []) if str(x).strip()] if isinstance(ex.get("transforms"), list) else []
                if not claim_type or not path:
                    continue
                values = select_all(agent_output, path)
                if required and not values:
                    issues.append({"type": "missing_required_data", "severity": "warning", "path": path, "message": f"Missing required field: {path}"})
                for v in values:
                    vv = _apply_transforms(v, transforms)
                    if vv is None:
                        continue
                    if isinstance(vv, str) and not vv.strip():
                        continue
                    claims.append(Claim(type=claim_type, value=vv, source_agent=agent_name, path=path))

            return claims, issues

        generic = cfg.get("generic") or {}
        if bool(generic.get("enabled", False)):
            try:
                max_depth = int(generic.get("max_depth", 5))
            except Exception:
                max_depth = 5
            items = flatten_primitives(agent_output, max_depth=max_depth)
            for it in items:
                p = str(it.get("path") or "").strip()
                val = it.get("value")
                if not p:
                    continue
                kind = "numeric" if isinstance(val, (int, float)) else "text"
                claims.append(Claim(type=str(kind), value=val, source_agent=agent_name, path=p))
            return claims, issues

        return claims, issues

