from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RxNormHit:
    name: str
    rxcui: str
    score: float


def lookup_rxnorm(term: str, timeout_s: float = 4.0) -> Optional[RxNormHit]:
    q = (term or "").strip()
    if not q:
        return None

    params = urllib.parse.urlencode({"term": q, "maxEntries": "1"})
    url = f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "MedLedgerAI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None

    candidates = (((payload or {}).get("approximateGroup") or {}).get("candidate") or [])
    if not candidates:
        return None

    c = candidates[0]
    rxcui = str(c.get("rxcui") or "").strip()
    score_raw = str(c.get("score") or "").strip()
    try:
        score = float(score_raw) / 100.0
    except Exception:
        score = 0.0
    if not rxcui:
        return None

    url_name = f"https://rxnav.nlm.nih.gov/REST/rxcui/{urllib.parse.quote(rxcui)}/property.json?propName=RxNorm%20Name"
    req2 = urllib.request.Request(url_name, headers={"User-Agent": "MedLedgerAI/1.0"})
    try:
        with urllib.request.urlopen(req2, timeout=timeout_s) as resp2:
            payload2 = json.loads(resp2.read().decode("utf-8", errors="replace"))
    except Exception:
        return None

    props = (((payload2 or {}).get("propConceptGroup") or {}).get("propConcept") or [])
    name = ""
    for p in props:
        if str(p.get("propName") or "") == "RxNorm Name":
            name = str(p.get("propValue") or "")
            break

    if not name:
        return None

    return RxNormHit(name=name, rxcui=rxcui, score=max(0.0, min(1.0, score)))
