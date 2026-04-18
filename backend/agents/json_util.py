"""Extract a JSON object from model text (strip markdown fences, salvage embedded JSON)."""

from __future__ import annotations

import json
from typing import Any


def _strip_fences(t: str) -> str:
    t = t.strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a single JSON object; raises ValueError / json.JSONDecodeError if impossible."""
    t = _strip_fences((text or "").strip())
    if not t:
        raise ValueError("model output empty (no JSON to parse)")

    def _loads(s: str) -> dict[str, Any] | None:
        try:
            val = json.loads(s)
        except json.JSONDecodeError:
            return None
        return val if isinstance(val, dict) else None

    if (out := _loads(t)) is not None:
        return out

    start = t.find("{")
    end = t.rfind("}")
    if 0 <= start < end:
        if (out := _loads(t[start : end + 1])) is not None:
            return out

    raise ValueError(f"could not parse JSON object from model output (prefix={t[:160]!r}…)")
