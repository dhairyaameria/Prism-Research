"""Extract text from PDF bytes (optional pymupdf)."""

from __future__ import annotations


def pdf_to_text(data: bytes) -> str:
    try:
        import fitz
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "pymupdf is not installed. Install API extras: pip install -e './apps/api[full]'"
        ) from e
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        parts: list[str] = []
        for page in doc:
            parts.append(page.get_text() or "")
        return "\n".join(parts).strip()
    finally:
        doc.close()
