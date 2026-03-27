import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

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
    model_name = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
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


def ocr_with_gemini(image_bytes: bytes, mime_type: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        import google.generativeai as genai
    except Exception:
        return None

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_VISION_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    model = genai.GenerativeModel(model_name)

    prompt = (
        "You are an OCR engine for handwritten medical prescriptions. "
        "Return only the transcribed text (no markdown, no extra commentary). "
        "Preserve line breaks where they help readability."
    )

    try:
        part: Any
        try:
            from google.generativeai.types import Part

            part = Part.from_data(data=image_bytes, mime_type=mime_type)
        except Exception:
            part = {"mime_type": mime_type, "data": image_bytes}

        resp = model.generate_content([prompt, part])
        raw = getattr(resp, "text", "") or ""
    except Exception:
        return None

    text = (raw or "").strip()
    if not text:
        return None

    text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def indian_payer_rules_fallback(raw_text: str, diagnoses: List[str], procedures: List[str], icd_codes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
    except Exception:
        return None

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    model = genai.GenerativeModel(model_name)

    def _codes_json(codes: List[Dict[str, Any]]) -> str:
        items: List[Dict[str, Any]] = []
        for c in codes:
            items.append({
                "code": c.get("code"),
                "description": c.get("description"),
                "score": c.get("score"),
                "source_text": c.get("source_text"),
            })
        return json.dumps(items, ensure_ascii=False)

    prompt = (
        "You are a medical coding auditor for Indian payers. Review the provided diagnoses, procedures, and ICD-10 codes.\n"
        "Return ONLY strict JSON with keys: issues (list of {type, severity, message}). Do not include markdown.\n"
        "Focus on payer policy conflicts, missing supporting diagnosis, incompatible code pairs, and code confidence concerns.\n\n"
        f"RAW_TEXT:\n{raw_text}\n\n"
        f"DIAGNOSES:\n{json.dumps(diagnoses, ensure_ascii=False)}\n\n"
        f"PROCEDURES:\n{json.dumps(procedures, ensure_ascii=False)}\n\n"
        f"ICD_CODES:\n{_codes_json(icd_codes)}\n"
    )
    try:
        resp = model.generate_content(prompt)
        raw = getattr(resp, "text", "") or ""
    except Exception:
        return None

    obj = _extract_json_object(raw)
    if not obj or not isinstance(obj, dict):
        return None
    issues = obj.get("issues")
    if not isinstance(issues, list):
        return None
    cleaned: List[Dict[str, Any]] = []
    for it in issues:
        if not isinstance(it, dict):
            continue
        t = str(it.get("type") or "external_advisory")
        sev = str(it.get("severity") or "warning").lower()
        msg = str(it.get("message") or "").strip()
        if msg:
            cleaned.append({"type": t, "severity": sev, "message": msg, "source": "gemini"})
    return {"issues": cleaned}

