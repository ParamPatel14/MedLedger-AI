from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.layers.denial_layer.config import get_denial_email
from app.models.denial import Claim, DenialEvent
from app.services.gemini import understand_denial_email
from app.services.gmail import GmailApiClient, extract_gmail_message_text


def _compile_patterns(items: Any) -> List[re.Pattern[str]]:
    pats: List[re.Pattern[str]] = []
    if not isinstance(items, list):
        return pats
    for it in items:
        s = str(it or "").strip()
        if not s:
            continue
        try:
            pats.append(re.compile(s, flags=re.IGNORECASE))
        except Exception:
            continue
    return pats


def _first_match(patterns: List[re.Pattern[str]], text: str) -> Optional[str]:
    for p in patterns:
        m = p.search(text)
        if not m:
            continue
        if m.groups():
            v = m.group(1)
        else:
            v = m.group(0)
        v = str(v or "").strip()
        if v:
            return v
    return None


def _all_matches(patterns: List[re.Pattern[str]], text: str) -> List[str]:
    out: List[str] = []
    for p in patterns:
        for m in p.finditer(text):
            v = m.group(1) if m.groups() else m.group(0)
            v = str(v or "").strip()
            if v:
                out.append(v)
    seen: set[str] = set()
    dedup: List[str] = []
    for v in out:
        key = v.upper()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(v)
    return dedup


@dataclass
class ParsedDenialEmail:
    claim_id: Optional[str]
    rejection_codes: List[str]
    raw_reason_text: str
    meta: Dict[str, Any]


class DenialEmailParser:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self._cfg = cfg or {}
        parsing = self._cfg.get("parsing") or {}
        self._claim_id_patterns = _compile_patterns(parsing.get("claim_id_patterns"))
        self._rej_patterns = _compile_patterns(parsing.get("rejection_code_patterns"))
        self._max_chars = int(parsing.get("max_text_chars", 8000) or 8000)
        gem = self._cfg.get("gemini") or {}
        self._gem_enabled = bool(gem.get("enabled"))
        self._gem_min_chars = int(gem.get("min_text_chars", 40) or 40)

    @classmethod
    def from_default(cls) -> "DenialEmailParser":
        return cls(get_denial_email())

    def parse_text(self, *, text: str, meta: Optional[Dict[str, Any]] = None) -> ParsedDenialEmail:
        raw = str(text or "").strip()
        if self._max_chars > 0 and len(raw) > self._max_chars:
            raw = raw[: self._max_chars]

        claim_id = _first_match(self._claim_id_patterns, raw)
        rejection_codes = _all_matches(self._rej_patterns, raw)

        gem: Optional[Dict[str, Any]] = None
        if self._gem_enabled and len(raw) >= self._gem_min_chars and (claim_id is None or not rejection_codes):
            try:
                gem = understand_denial_email(raw)
            except Exception:
                gem = None

        if gem:
            if claim_id is None:
                cid = gem.get("claim_id")
                if cid:
                    claim_id = str(cid).strip() or None
            if not rejection_codes:
                codes = gem.get("rejection_codes")
                if isinstance(codes, list):
                    rejection_codes = [str(c or "").strip() for c in codes if str(c or "").strip()]

        m = dict(meta or {})
        if gem:
            m["gemini"] = gem

        return ParsedDenialEmail(
            claim_id=claim_id,
            rejection_codes=rejection_codes,
            raw_reason_text=raw,
            meta=m,
        )

    def parse_gmail_message(self, message: Dict[str, Any]) -> ParsedDenialEmail:
        mt = extract_gmail_message_text(message)
        text = "\n\n".join([str(mt.get("subject") or ""), str(mt.get("body_text") or ""), str(mt.get("snippet") or "")]).strip()
        return self.parse_text(text=text, meta={"source": "gmail", **mt})


class DenialEmailIngestionService:
    def __init__(self) -> None:
        self._cfg = get_denial_email()
        self._parser = DenialEmailParser(self._cfg)

    def ingest_gmail(
        self,
        db: Session,
        *,
        query: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        run_agent: bool = False,
    ) -> Dict[str, Any]:
        gmail_cfg = self._cfg.get("gmail") or {}
        if not bool(gmail_cfg.get("enabled")):
            return {"status": "disabled", "ingested": [], "ran_agent": False}

        client = GmailApiClient.from_env()
        if client is None:
            return {"status": "missing_credentials", "ingested": [], "ran_agent": False}

        q = str(query or gmail_cfg.get("default_query") or "").strip()
        lids = label_ids if isinstance(label_ids, list) else gmail_cfg.get("label_ids") or []
        lids = [str(x).strip() for x in lids if str(x).strip()]
        mr = int(max_results or gmail_cfg.get("max_results") or 10)

        msgs = client.list_messages(query=q, label_ids=lids, max_results=mr)

        ingested: List[Dict[str, Any]] = []
        from app.layers.denial_layer.service import DenialManagementAgent

        agent = DenialManagementAgent() if run_agent else None

        for m in msgs:
            mid = str(m.get("id") or "").strip()
            if not mid:
                continue
            full = client.get_message(mid)
            parsed = self._parser.parse_gmail_message(full)

            claim: Optional[Claim] = None
            if parsed.claim_id:
                claim = db.query(Claim).filter(Claim.id == parsed.claim_id).first()
            if claim is None:
                claim = Claim(status="denied", record_id=None, claim_data={"source_meta": parsed.meta})
                db.add(claim)
                db.commit()
                db.refresh(claim)

            existing = db.query(DenialEvent).filter(DenialEvent.claim_id == claim.id).all()
            if any(isinstance(getattr(ev, "source_meta", None), dict) and ev.source_meta.get("gmail_message_id") == parsed.meta.get("gmail_message_id") for ev in existing):
                ingested.append({"gmail_message_id": parsed.meta.get("gmail_message_id"), "claim_id": claim.id, "status": "skipped_duplicate"})
                continue

            ev = DenialEvent(
                claim_id=claim.id,
                status="denied",
                raw_reason_text=parsed.raw_reason_text,
                rejection_codes=parsed.rejection_codes,
                structured_reasons=[],
                source_meta=parsed.meta,
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)

            agent_out: Optional[Dict[str, Any]] = None
            if agent is not None:
                try:
                    agent_out = agent.run_for_denial_event(db, claim_id=claim.id, denial_event_id=ev.id)
                except Exception as e:
                    agent_out = {"status": "error", "error": str(e)}

            ingested.append(
                {
                    "gmail_message_id": parsed.meta.get("gmail_message_id"),
                    "claim_id": claim.id,
                    "denial_event_id": ev.id,
                    "parsed": {
                        "claim_id": parsed.claim_id,
                        "rejection_codes": parsed.rejection_codes,
                    },
                    "agent": agent_out,
                }
            )

        return {"status": "ok", "ingested": ingested, "ran_agent": bool(run_agent)}

