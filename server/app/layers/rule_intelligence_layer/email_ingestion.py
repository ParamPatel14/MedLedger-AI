from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.layers.rule_intelligence_layer.config import get_rule_extraction_config
from app.layers.rule_intelligence_layer.types import RuleSourceDocument
from app.services.gmail import GmailApiClient, extract_gmail_message_text


def _compile(items: Any) -> List[re.Pattern[str]]:
    out: List[re.Pattern[str]] = []
    if isinstance(items, list):
        for it in items:
            try:
                out.append(re.compile(str(it), re.IGNORECASE | re.MULTILINE))
            except Exception:
                continue
    return out


def guess_tpa_name(*, subject: str, sender: str) -> str:
    cfg = get_rule_extraction_config()
    tpa_cfg = (cfg.get("tpa_detection") or {}) if isinstance(cfg, dict) else {}
    patterns = _compile(tpa_cfg.get("patterns") or [])
    text = "\n".join([str(subject or ""), str(sender or "")]).strip()
    for p in patterns:
        m = p.search(text)
        if not m:
            continue
        if m.groups():
            v = str(m.group(1) or "").strip()
            if v:
                return v
        v = str(m.group(0) or "").strip()
        if v:
            return v
    return ""


def build_email_source_document(*, tpa_name: str, subject: str, sender: str, body_text: str, meta: Optional[Dict[str, Any]] = None) -> RuleSourceDocument:
    tpa = str(tpa_name or "").strip() or guess_tpa_name(subject=subject, sender=sender)
    text = "\n\n".join([str(subject or "").strip(), str(body_text or "").strip()]).strip()
    return RuleSourceDocument(source="email", tpa_name=tpa, text=text, meta=meta or {})


def pull_gmail_policy_updates(*, query: str, label_ids: List[str], max_results: int) -> List[RuleSourceDocument]:
    client = GmailApiClient.from_env()
    if client is None:
        return []
    cfg = get_rule_extraction_config()
    email_cfg = (cfg.get("email") or {}) if isinstance(cfg, dict) else {}
    q = str(query or "").strip() or str(email_cfg.get("default_query") or "").strip()
    labels = label_ids if isinstance(label_ids, list) and label_ids else (email_cfg.get("label_ids") or [])
    max_n = int(max_results or 0) or int(email_cfg.get("max_results") or 10)

    docs: List[RuleSourceDocument] = []
    for m in client.list_messages(query=q, label_ids=labels, max_results=max_n):
        mid = str(m.get("id") or "").strip()
        if not mid:
            continue
        raw = client.get_message(mid)
        parsed = extract_gmail_message_text(raw)
        docs.append(
            build_email_source_document(
                tpa_name="",
                subject=str(parsed.get("subject") or ""),
                sender=str(parsed.get("from") or ""),
                body_text=str(parsed.get("body_text") or ""),
                meta={
                    "gmail_message_id": parsed.get("gmail_message_id"),
                    "gmail_thread_id": parsed.get("gmail_thread_id"),
                    "from": parsed.get("from"),
                    "subject": parsed.get("subject"),
                    "date": parsed.get("date"),
                    "snippet": parsed.get("snippet"),
                    "received_at": datetime.utcnow().isoformat(),
                },
            )
        )
    return docs
