"""One LLM call: claims + contradictions from top chunks."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from backend.agents.json_util import parse_json_object
from backend.agents.llm_one import complete_one
from backend.agents.tenant_retriever import RetrievedChunk

logger = logging.getLogger(__name__)

_SYSTEM = """You are a financial analysis agent. Given evidence chunks,
simultaneously: (1) extract claims with chunk index and confidence,
(2) identify contradictions between management statements and
disclosures. Chunks may include external live web results (body starts with "[You.com" or title contains "You.com |");
use those chunk_index values when a claim is grounded in web context. Return only JSON:
{"claims": [{"claim": "string", "chunk_index": 0, "confidence": 0.0}],
 "contradictions": [{"claim_a": "string", "claim_b": "string", "tension_type": "string", "severity": "low|med|high"}]}"""


def _format_chunks(chunks: list[RetrievedChunk], *, max_chunks: int = 9, max_chars: int = 320) -> str:
    lines: list[str] = []
    for c in chunks[:max_chunks]:
        body = (c.body or "")[:max_chars].replace("\n", " ")
        lines.append(f"[index={c.index} id={c.chunk_id}] {body}")
    return "\n".join(lines)


_LLM_HOP_TEXT_MAX = 65536


def _clip_llm_text(s: str) -> str | None:
    if not s:
        return None
    if len(s) <= _LLM_HOP_TEXT_MAX:
        return s
    return s[:_LLM_HOP_TEXT_MAX] + "\n… [truncated for storage]"


async def run_analysis(model_id: str, chunks: list[RetrievedChunk], *, question: str) -> tuple[dict[str, Any], dict[str, Any], int]:
    """Returns (hop_payload, {claims, contradictions}, duration_ms)."""
    t0 = time.perf_counter()
    user = f"Question: {question}\n\nEvidence chunks:\n{_format_chunks(chunks)}"
    raw = ""
    try:
        raw = await complete_one(model_id, system=_SYSTEM, user=user, json_mode=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("Analysis LLM call failed: %s", e)
        data = {"claims": [], "contradictions": []}
    else:
        try:
            data = parse_json_object(raw)
        except (ValueError, json.JSONDecodeError, TypeError) as e:
            logger.warning("Analysis JSON parse failed: %s preview=%r", e, (raw or "")[:400])
            data = {"claims": [], "contradictions": []}
    claims = data.get("claims") if isinstance(data.get("claims"), list) else []
    cxs = data.get("contradictions") if isinstance(data.get("contradictions"), list) else []
    ms = int((time.perf_counter() - t0) * 1000)
    hop_payload = {
        "agent": "Analysis",
        "intent": "claims_and_contradictions",
        "claim_count": len(claims),
        "contradiction_count": len(cxs),
        "llm_response_text": _clip_llm_text(raw),
    }
    logger.info("Analysis: claims=%s contradictions=%s", len(claims), len(cxs))
    if not claims and not cxs:
        logger.warning(
            "Analysis produced no claims or contradictions (check PRISM_ADK_MODEL / Baseten slug and API logs)."
        )
    return hop_payload, {"claims": claims, "contradictions": cxs}, ms
