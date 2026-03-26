import json
import os
import re
from typing import Any, Dict, List, Optional

from app.models.schemas import ProcessResponse


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def extract_with_gemini(text: str) -> Optional[ProcessResponse]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        import google.generativeai as genai
    except Exception:
        return None

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
    model = genai.GenerativeModel(model_name)

    prompt = (
        "Extract structured clinical data from the input clinical note. "
        "Return ONLY valid JSON with keys: diagnosis (array of strings), procedures (array of strings), medications (array of strings). "
        "No extra keys, no markdown.\n\n"
        f"TEXT:\n{text}\n"
    )

    try:
        resp = model.generate_content(prompt)
        raw = getattr(resp, "text", "") or ""
    except Exception:
        return None

    obj = _extract_json_object(raw)
    if not obj:
        return None

    def _arr(key: str) -> List[str]:
        v = obj.get(key)
        if not isinstance(v, list):
            return []
        out: List[str] = []
        for item in v:
            s = str(item).strip().lower()
            if s:
                out.append(s)
        return out

    return ProcessResponse(
        diagnosis=_arr("diagnosis"),
        procedures=_arr("procedures"),
        medications=_arr("medications"),
        entities=None,
    )

