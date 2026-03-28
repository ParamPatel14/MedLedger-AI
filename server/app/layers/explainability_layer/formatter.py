from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.layers.explainability_layer.config import get_explainability_templates


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


class _SafeMap(dict):
    def __missing__(self, key: str) -> str:
        return ""


@dataclass(frozen=True)
class FormattedExplanation:
    text: str
    template_id: str
    meta: Dict[str, Any]


class ExplanationFormatter:
    def __init__(self) -> None:
        self._cfg = get_explainability_templates()

    @property
    def version(self) -> str:
        return str((self._cfg.get("version") or "") if isinstance(self._cfg, dict) else "")

    def format(self, *, template_id: str, params: Optional[Dict[str, Any]] = None) -> FormattedExplanation:
        cfg = self._cfg if isinstance(self._cfg, dict) else {}
        templates = cfg.get("templates") if isinstance(cfg.get("templates"), dict) else {}
        entry = templates.get(str(template_id or "").strip()) if isinstance(templates, dict) else None
        if not isinstance(entry, dict) or entry.get("enabled") is False:
            return FormattedExplanation(text="", template_id=str(template_id or ""), meta={"missing_template": True})
        tpl = _as_str(entry.get("template") or "")
        try:
            txt = tpl.format_map(_SafeMap(params or {}))
        except Exception:
            txt = ""
        return FormattedExplanation(text=txt, template_id=str(template_id or ""), meta={"missing_template": not bool(txt)})

