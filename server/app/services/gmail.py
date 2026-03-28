from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GmailClientConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    user_id: str


def _b64url_decode(data: str) -> bytes:
    s = str(data or "")
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _headers_map(headers: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not isinstance(headers, list):
        return out
    for h in headers:
        if not isinstance(h, dict):
            continue
        name = str(h.get("name") or "").strip().lower()
        value = str(h.get("value") or "").strip()
        if name:
            out[name] = value
    return out


def _strip_html(text: str) -> str:
    t = str(text or "")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?is)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</p\s*>", "\n", t)
    t = re.sub(r"(?is)<[^>]+>", " ", t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def extract_gmail_message_text(message: Dict[str, Any], *, prefer_plain: bool = True) -> Dict[str, Any]:
    payload = message.get("payload") if isinstance(message, dict) else None
    payload = payload if isinstance(payload, dict) else {}
    headers = _headers_map(payload.get("headers"))
    subject = headers.get("subject", "")
    sender = headers.get("from", "")
    date = headers.get("date", "")
    thread_id = str(message.get("threadId") or "")
    message_id = str(message.get("id") or "")
    snippet = str(message.get("snippet") or "")

    parts: List[Dict[str, Any]] = []
    stack = [payload] if payload else []
    while stack:
        p = stack.pop()
        if not isinstance(p, dict):
            continue
        if isinstance(p.get("parts"), list):
            for child in reversed(p.get("parts") or []):
                if isinstance(child, dict):
                    stack.append(child)
        parts.append(p)

    def _part_text(mime: str) -> Optional[str]:
        for p in parts:
            if str(p.get("mimeType") or "").lower() != mime:
                continue
            body = p.get("body")
            if not isinstance(body, dict):
                continue
            data = body.get("data")
            if not data:
                continue
            try:
                return _b64url_decode(str(data)).decode("utf-8", errors="replace")
            except Exception:
                continue
        return None

    body_plain = _part_text("text/plain")
    body_html = _part_text("text/html")
    if prefer_plain and body_plain:
        body_text = body_plain.strip()
    elif body_html:
        body_text = _strip_html(body_html)
    else:
        body_text = (body_plain or body_html or snippet or "").strip()

    return {
        "gmail_message_id": message_id,
        "gmail_thread_id": thread_id,
        "subject": subject,
        "from": sender,
        "date": date,
        "snippet": snippet,
        "body_text": body_text,
    }


class GmailApiClient:
    def __init__(self, cfg: GmailClientConfig) -> None:
        self._cfg = cfg
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    @staticmethod
    def from_env() -> Optional["GmailApiClient"]:
        client_id = (os.getenv("GMAIL_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("GMAIL_CLIENT_SECRET") or "").strip()
        refresh_token = (os.getenv("GMAIL_REFRESH_TOKEN") or "").strip()
        user_id = (os.getenv("GMAIL_USER_ID") or "").strip() or "me"
        if not (client_id and client_secret and refresh_token):
            return None
        return GmailApiClient(GmailClientConfig(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token, user_id=user_id))

    def _refresh_access_token(self) -> str:
        now = time.time()
        if self._token and now < (self._token_expiry - 30):
            return self._token

        payload = urllib.parse.urlencode(
            {
                "client_id": self._cfg.client_id,
                "client_secret": self._cfg.client_secret,
                "refresh_token": self._cfg.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        obj = json.loads(raw)
        token = str(obj.get("access_token") or "")
        expires_in = float(obj.get("expires_in") or 3600)
        if not token:
            raise RuntimeError("Failed to refresh Gmail access token")
        self._token = token
        self._token_expiry = now + expires_in
        return token

    def _get_json(self, url: str) -> Dict[str, Any]:
        token = self._refresh_access_token()
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        obj = json.loads(raw) if raw.strip() else {}
        return obj if isinstance(obj, dict) else {}

    def list_messages(self, *, query: str, label_ids: List[str], max_results: int) -> List[Dict[str, Any]]:
        q = str(query or "").strip()
        params: Dict[str, Any] = {"q": q, "maxResults": int(max_results or 10), "includeSpamTrash": "false"}
        for lid in label_ids or []:
            if str(lid).strip():
                params.setdefault("labelIds", [])
                params["labelIds"].append(str(lid).strip())
        url = f"https://gmail.googleapis.com/gmail/v1/users/{urllib.parse.quote(self._cfg.user_id)}/messages?{urllib.parse.urlencode(params, doseq=True)}"
        obj = self._get_json(url)
        msgs = obj.get("messages")
        if not isinstance(msgs, list):
            return []
        out: List[Dict[str, Any]] = []
        for m in msgs:
            if isinstance(m, dict) and m.get("id"):
                out.append(m)
        return out

    def get_message(self, message_id: str) -> Dict[str, Any]:
        mid = str(message_id or "").strip()
        if not mid:
            return {}
        url = f"https://gmail.googleapis.com/gmail/v1/users/{urllib.parse.quote(self._cfg.user_id)}/messages/{urllib.parse.quote(mid)}?format=full"
        return self._get_json(url)

