from __future__ import annotations

import io
from typing import Any, Dict, Optional

from app.layers.rule_intelligence_layer.types import RuleSourceDocument


def extract_pdf_text(data: bytes) -> str:
    blob = data or b""
    if not blob:
        return ""
    try:
        import pdfplumber

        out: list[str] = []
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                if txt.strip():
                    out.append(txt)
        return "\n\n".join(out).strip()
    except Exception:
        pass

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=blob, filetype="pdf")
        out: list[str] = []
        for i in range(int(doc.page_count)):
            page = doc.load_page(i)
            txt = page.get_text("text") or ""
            if txt.strip():
                out.append(txt)
        return "\n\n".join(out).strip()
    except Exception:
        return ""


def build_pdf_source_document(*, tpa_name: str, filename: str, pdf_bytes: bytes, meta: Optional[Dict[str, Any]] = None) -> RuleSourceDocument:
    text = extract_pdf_text(pdf_bytes)
    return RuleSourceDocument(
        source="pdf",
        tpa_name=str(tpa_name or "").strip(),
        text=text,
        source_ref=str(filename or "").strip(),
        meta=meta or {},
    )
