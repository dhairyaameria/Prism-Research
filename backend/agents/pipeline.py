"""Fast Prism pipeline: research (no LLM) → analysis (1 LLM) → thesis (1 LLM); yields SSE dicts per hop."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.analysis_agent import run_analysis
from backend.agents.research_agent import run_research
from backend.agents.thesis_agent import run_thesis
from prism_api.models import Contradiction, Hop, Run
from prism_api.services.quality_gate import evaluate_thesis_quality

logger = logging.getLogger(__name__)


async def stream_fast_pipeline(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    ticker: str,
    question: str,
    model_id: str,
) -> AsyncIterator[dict[str, Any]]:
    """Assume `run` is already `running` (set by run_service)."""
    run = await db.get(Run, run_id)
    if not run:
        yield {"event": "error", "message": "run not found"}
        return

    t_pipeline = time.perf_counter()

    # --- Research (no LLM): pgvector + optional You.com YDC ---
    yield {
        "event": "phase",
        "phase": "research",
        "message": "Embedding + vector retrieval + You.com live search when YOU_API_KEY is set (no LLM)",
    }
    hop_r, chunks, ms_r = await run_research(
        db, tenant_id=run.tenant_id, ticker=ticker, question=question
    )
    db.add(
        Hop(
            run_id=run_id,
            agent="Research",
            intent=str(hop_r.get("intent") or "vector_retrieval"),
            payload=hop_r,
            duration_ms=ms_r,
        )
    )
    await db.flush()
    yield {"event": "hop", "agent": "Research", "payload": hop_r, "duration_ms": ms_r}

    # --- Analysis (1 LLM) ---
    yield {"event": "phase", "phase": "analysis", "message": "Single LLM: claims + contradictions"}
    hop_a, analysis, ms_a = await run_analysis(model_id, chunks, question=question)
    db.add(
        Hop(
            run_id=run_id,
            agent="Analysis",
            intent="claims_and_contradictions",
            payload={**hop_a, "claims_n": len(analysis.get("claims") or [])},
            duration_ms=ms_a,
        )
    )
    for c in analysis.get("contradictions") or []:
        if not isinstance(c, dict):
            continue
        desc = f"{c.get('claim_a', '')} vs {c.get('claim_b', '')}"[:4000]
        db.add(
            Contradiction(
                run_id=run_id,
                tension_type=str(c.get("tension_type", "other"))[:64],
                description=desc,
                side_a_citation_ids=[str(c.get("claim_a", ""))[:200]],
                side_b_citation_ids=[str(c.get("claim_b", ""))[:200]],
            )
        )
    await db.flush()
    yield {"event": "hop", "agent": "Analysis", "payload": hop_a, "duration_ms": ms_a}

    # --- Thesis (1 LLM) ---
    yield {"event": "phase", "phase": "thesis", "message": "Single LLM: stance + summary + bull/bear"}
    hop_t, _thesis_json, ms_t = await run_thesis(db, run, model_id, analysis, chunks)
    db.add(
        Hop(
            run_id=run_id,
            agent="Thesis",
            intent="thesis_json",
            payload=hop_t,
            duration_ms=ms_t,
        )
    )

    cx_list = analysis.get("contradictions") if isinstance(analysis.get("contradictions"), list) else []
    claims_list = analysis.get("claims") if isinstance(analysis.get("claims"), list) else []
    claim_n = len([x for x in claims_list if isinstance(x, dict)])
    qp, qrep = evaluate_thesis_quality(
        thesis=run.thesis_json or {},
        contradiction_count=len([x for x in cx_list if isinstance(x, dict)]),
        claim_count=claim_n,
    )
    run.quality_passed = qp
    run.quality_report = qrep

    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    await db.commit()

    elapsed_ms = int((time.perf_counter() - t_pipeline) * 1000)
    logger.info("fast pipeline run %s completed in %sms", run_id, elapsed_ms)
    yield {"event": "completed", "run_id": str(run_id), "elapsed_ms": elapsed_ms}


async def execute_fast_pipeline(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    ticker: str,
    question: str,
    model_id: str,
) -> None:
    """Non-streaming: consume generator side effects only."""
    async for _ in stream_fast_pipeline(
        db, run_id=run_id, ticker=ticker, question=question, model_id=model_id
    ):
        pass
