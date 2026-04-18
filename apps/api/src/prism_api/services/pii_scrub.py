"""Lightweight PII redaction for analyst feedback (regex-based; not a legal guarantee)."""

from __future__ import annotations

import re


_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def scrub_text(text: str) -> str:
    if not text:
        return ""
    t = _SSN.sub("[REDACTED-SSN]", text)
    t = _CC.sub("[REDACTED-PAN]", t)
    t = _EMAIL.sub("[REDACTED-EMAIL]", t)
    t = _PHONE.sub("[REDACTED-PHONE]", t)
    return t
