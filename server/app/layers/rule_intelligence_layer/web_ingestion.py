from __future__ import annotations

import html
import re
import urllib.request
from typing import Any, Dict, Optional

from app.layers.rule_intelligence_layer.types import RuleSourceDocument


def _strip_html(text: str) -> str:
    raw = str(text or "")
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        out = soup.get_text(separator="\n")
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()
    except Exception:
        pass

    raw = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\\1>", " ", raw)
    raw = re.sub(r"(?is)<br\\s*/?>", "\n", raw)
    raw = re.sub(r"(?is)</p\\s*>", "\n", raw)
    raw = re.sub(r"(?is)<.*?>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t]{2,}", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def fetch_url_text(url: str, *, timeout_s: int = 20, user_agent: str = "MedLedgerRuleBot/1.0") -> str:
    u = str(url or "").strip()
    if not u:
        return ""
    req = urllib.request.Request(u, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=float(timeout_s)) as resp:
        data = resp.read()
    try:
        decoded = data.decode("utf-8", errors="ignore")
    except Exception:
        decoded = str(data)
    return _strip_html(decoded)


def build_web_source_document(*, tpa_name: str, url: str, meta: Optional[Dict[str, Any]] = None) -> RuleSourceDocument:
    text = fetch_url_text(url)
    return RuleSourceDocument(source="web", tpa_name=str(tpa_name or "").strip(), text=text, source_ref=str(url or "").strip(), meta=meta or {})
