from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.layers.explainability_layer.config import get_explainability_rules
from app.layers.explainability_layer.formatter import ExplanationFormatter
from app.layers.explainability_layer.types import ExplanationItem
from app.layers.governance_layer.evaluation import DecisionInputs, evaluate_condition, first_value, get_values


def _as_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def _select_from(ctx: Dict[str, Any], item: Any, path: str) -> Any:
    p = _as_str(path).strip()
    if not p:
        return None
    if p == "item":
        return item
    if p.startswith("item."):
        key = p[len("item.") :]
        return first_value(item, key, transforms=["string"])
    return first_value(ctx, p, transforms=["string"])


class DecisionExplanationEngine:
    def __init__(self) -> None:
        self._cfg = get_explainability_rules()
        self._formatter = ExplanationFormatter()

    @property
    def templates_version(self) -> str:
        return self._formatter.version

    @property
    def rules_version(self) -> str:
        return str((self._cfg.get("version") or "") if isinstance(self._cfg, dict) else "")

    def explain(self, *, ctx: Dict[str, Any]) -> List[ExplanationItem]:
        cfg = self._cfg if isinstance(self._cfg, dict) else {}
        rules = cfg.get("rules") if isinstance(cfg.get("rules"), list) else []

        decision_inputs = DecisionInputs(
            raw_text=_as_str(ctx.get("raw_text") or ""),
            workflow_confidence=_as_float(ctx.get("workflow_confidence") or 0.0),
            svm=_as_dict(ctx.get("svm") or {}),
            policy_issues=list(_as_dict(ctx.get("governance") or {}).get("issues") or []),
            edge_issues=[],
            external_issues=list(_as_dict(ctx.get("validation") or {}).get("issues") or []),
        )

        out: List[ExplanationItem] = []
        for r in rules:
            if not isinstance(r, dict) or r.get("enabled") is False:
                continue
            when = r.get("when") or {}
            if not isinstance(when, dict):
                continue
            if not evaluate_condition(when, ctx=ctx, decision_inputs=decision_inputs):
                continue

            emit = r.get("emit") or {}
            if not isinstance(emit, dict):
                continue

            exp_type = _as_str(r.get("type") or emit.get("type") or "").strip()
            template_id = _as_str(emit.get("template_id") or "").strip()
            if not exp_type or not template_id:
                continue

            items_path = _as_str(emit.get("items_path") or "").strip()
            items = get_values(ctx, items_path) if items_path else [None]

            params_cfg = emit.get("params") if isinstance(emit.get("params"), dict) else {}
            confidence_path = _as_str(emit.get("confidence_path") or "").strip()
            fallback_conf = _as_float(emit.get("confidence") or 0.0)

            for item in items:
                params: Dict[str, Any] = {}
                for k, p in params_cfg.items():
                    if not _as_str(k).strip():
                        continue
                    params[str(k)] = _select_from(ctx, item, _as_str(p))

                conf = fallback_conf
                if confidence_path:
                    conf_val = _select_from(ctx, item, confidence_path)
                    conf = _as_float(conf_val) if conf_val is not None else conf

                formatted = self._formatter.format(template_id=template_id, params=params)
                out.append(
                    ExplanationItem(
                        type=exp_type,
                        explanation=formatted.text,
                        confidence=float(conf),
                        meta={
                            "rule_id": _as_str(r.get("id") or ""),
                            "template_id": formatted.template_id,
                            "template_meta": formatted.meta,
                            "params": params,
                        },
                    )
                )

        return out

