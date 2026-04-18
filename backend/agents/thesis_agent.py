"""One LLM call: thesis from claims + contradictions; persist thesis_json, matrix, citations."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.json_util import parse_json_object
from backend.agents.llm_one import complete_one
from backend.agents.tenant_retriever import RetrievedChunk
from prism_api.models import Citation, MatrixRow, Run

logger = logging.getLogger(__name__)

_LLM_HOP_TEXT_MAX = 65536


def _clip_llm_text(s: str) -> str | None:
    if not s:
        return None
    if len(s) <= _LLM_HOP_TEXT_MAX:
        return s
    return s[:_LLM_HOP_TEXT_MAX] + "\n… [truncated for storage]"


_SYSTEM = """You are an investment thesis agent. From these pre-extracted
claims and contradictions produce a structured thesis.
Return only JSON:
{"stance": "BULL" or "BEAR" or "NEUTRAL",
 "summary": "2-4 sentences",
 "bull_points": [{"text": "string", "chunk_index": 0, "confidence": 0.0}],
 "bear_points": [{"text": "string", "chunk_index": 0, "confidence": 0.0}]}"""


def _compact_json(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _chunk_uuid_by_index(chunks: list[RetrievedChunk]) -> dict[int, uuid.UUID]:
    return {c.index: c.chunk_id for c in chunks}


def _index_to_uuid(mapping: dict[int, uuid.UUID], idx: Any) -> uuid.UUID | None:
    try:
        i = int(idx)
    except (TypeError, ValueError):
        return None
    return mapping.get(i)


def _chunk_at_index(chunks: list[RetrievedChunk], idx: Any) -> RetrievedChunk | None:
    try:
        i = int(idx)
    except (TypeError, ValueError):
        return None
    return next((c for c in chunks if c.index == i), None)


async def run_thesis(
    session: AsyncSession,
    run: Run,
    model_id: str,
    analysis: dict[str, Any],
    chunks: list[RetrievedChunk],
) -> tuple[dict[str, Any], dict[str, Any], int]:
    """Set run.thesis_json; add MatrixRow + Citation rows. Returns (hop_payload, thesis_json, duration_ms)."""
    t0 = time.perf_counter()
    user = _compact_json(
        {"claims": analysis.get("claims", []), "contradictions": analysis.get("contradictions", [])}
    )
    llm_ok = True
    parse_ok = True
    raw = ""
    try:
        raw = await complete_one(model_id, system=_SYSTEM, user=user, json_mode=True)
    except Exception as e:  # noqa: BLE001
        llm_ok = False
        parse_ok = False
        logger.warning("Thesis LLM call failed: %s", e)

    fallback: dict[str, Any] = {
        "stance": "NEUTRAL",
        "summary": "Thesis model output was missing or not valid JSON; see matrix rows from extracted claims.",
        "bull_points": [],
        "bear_points": [],
    }
    if llm_ok and (raw or "").strip():
        try:
            data = parse_json_object(raw)
        except (ValueError, json.JSONDecodeError, TypeError) as e:
            parse_ok = False
            logger.warning("Thesis JSON parse failed: %s preview=%r", e, (raw or "")[:400])
            data = dict(fallback)
    else:
        if llm_ok:
            parse_ok = False
            logger.warning("Thesis empty model output after successful HTTP call")
        data = dict(fallback)
    ms = int((time.perf_counter() - t0) * 1000)

    stance_raw = str(data.get("stance", "NEUTRAL")).upper()
    stance = stance_raw.lower() if stance_raw in ("BULL", "BEAR", "NEUTRAL") else "neutral"
    summary = str(data.get("summary", "")).strip()
    bull = data.get("bull_points") if isinstance(data.get("bull_points"), list) else []
    bear = data.get("bear_points") if isinstance(data.get("bear_points"), list) else []

    idx_map = _chunk_uuid_by_index(chunks)

    def _matrix_chunk_indices(rows: list[dict[str, Any]]) -> set[int]:
        out: set[int] = set()
        for m in rows:
            for lab in m.get("citation_labels") or []:
                if isinstance(lab, str) and lab.startswith("chunk#"):
                    try:
                        out.add(int(lab.split("#", 1)[1]))
                    except (ValueError, IndexError):
                        pass
        return out

    matrix_rows: list[dict[str, Any]] = []
    for i, row in enumerate((analysis.get("claims") or [])[:8]):
        if not isinstance(row, dict):
            continue
        claim = str(row.get("claim", ""))[:400]
        ci = row.get("chunk_index", i)
        ch = _chunk_at_index(chunks, ci)
        citation_labels = (
            ["you_com", f"chunk#{ci}"]
            if ch is not None and ch.is_external
            else [f"chunk#{ci}"]
        )
        matrix_rows.append(
            {
                "theme": claim[:80] or f"theme_{i}",
                "summary": claim,
                "confidence": float(row.get("confidence") or 0.5),
                "evidence": claim[:300],
                "citation_labels": citation_labels,
            }
        )

    # Dedicated matrix rows for You.com snippets not already tied to a claim row (same chunk index).
    covered = _matrix_chunk_indices(matrix_rows)
    you_extra = 0
    for c in chunks:
        if not c.is_external:
            continue
        if c.index in covered:
            continue
        if you_extra >= 6:
            break
        title = ((c.doc_title or "You.com").split("\n", 1)[0])[:100]
        body_ex = ((c.body or "")[:320]).replace("\n", " ").strip()
        matrix_rows.append(
            {
                "theme": f"You.com · {title}"[:120],
                "summary": body_ex or "(empty snippet)",
                "confidence": round(float(c.score or 0.55), 3),
                "evidence": body_ex[:300],
                "citation_labels": ["you_com", f"chunk#{c.index}"],
            }
        )
        covered.add(c.index)
        you_extra += 1

    if not matrix_rows and chunks:
        c0 = chunks[0]
        excerpt = ((c0.body or "")[:400]).replace("\n", " ")
        matrix_rows.append(
            {
                "theme": "Retrieved evidence (analysis returned no claims)",
                "summary": excerpt or "(empty chunk)",
                "confidence": 0.25,
                "evidence": excerpt[:300],
                "citation_labels": [f"chunk#{c0.index}"],
            }
        )

    thesis_json: dict[str, Any] = {
        "stance": stance,
        "narrative": summary,
        "matrix_rows": matrix_rows,
        "bull_points": bull,
        "bear_points": bear,
    }
    run.thesis_json = thesis_json

    for order, m in enumerate(matrix_rows):
        session.add(
            MatrixRow(
                run_id=run.id,
                theme=str(m.get("theme", "")),
                summary=str(m.get("summary", "")),
                confidence=float(m.get("confidence") or 0.0),
                evidence=str(m.get("evidence", "")),
                citation_ids=list(m.get("citation_labels") or []),
                row_order=order,
            )
        )

    cit_order = 0
    for label, points in (("bull", bull), ("bear", bear)):
        for p in points:
            if not isinstance(p, dict):
                continue
            ch = _chunk_at_index(chunks, p.get("chunk_index"))
            cid = _index_to_uuid(idx_map, p.get("chunk_index"))
            if ch is not None and ch.is_external:
                cid = None
            session.add(
                Citation(
                    run_id=run.id,
                    citation_id=f"{label}_{cit_order}",
                    source_kind="you_com" if ch is not None and ch.is_external else "internal_chunk",
                    chunk_id=cid,
                    doc_title=ch.doc_title if ch is not None and ch.is_external else None,
                    quote_span=str(p.get("text", ""))[:800],
                    retrieval_score=float(p.get("confidence") or 0.0),
                    used_by_agent="ThesisAgent",
                    hop_id=None,
                    extra={},
                )
            )
            cit_order += 1

    hop_payload = {
        "agent": "Thesis",
        "intent": "thesis_json",
        "stance": stance,
        "bull_n": len(bull),
        "bear_n": len(bear),
        "matrix_n": len(matrix_rows),
        "llm_ok": llm_ok,
        "json_parse_ok": parse_ok,
        "llm_response_text": _clip_llm_text(raw),
    }
    logger.info(
        "Thesis: stance=%s matrix=%s bull=%s bear=%s llm_ok=%s json_ok=%s",
        stance,
        len(matrix_rows),
        len(bull),
        len(bear),
        llm_ok,
        parse_ok,
    )
    return hop_payload, thesis_json, ms
