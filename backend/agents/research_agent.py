"""Research hop: embed query + vector search + rerank — no LLM call."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.ollama_client import embed_query as ollama_embed_query
from backend.agents.tenant_retriever import RetrievedChunk, TenantRetriever
from prism_api.integrations.you_com import ydc_snippets_from_payload, you_search_sync
from prism_api.services.embeddings import embed_texts, embeddings_enabled

logger = logging.getLogger(__name__)


def _renumber_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            index=i,
            chunk_id=c.chunk_id,
            body=c.body,
            doc_title=c.doc_title,
            score=c.score,
            is_external=c.is_external,
        )
        for i, c in enumerate(chunks)
    ]


async def _you_com_chunks(*, ticker: str, question: str) -> list[RetrievedChunk]:
    if os.environ.get("PRISM_FAST_PIPELINE_YOU", "1").lower() in ("0", "false", "no"):
        return []
    if not os.environ.get("YOU_API_KEY", "").strip():
        return []
    q = f"{ticker.upper()} stock {question}".strip()[:480]
    try:
        payload = await asyncio.to_thread(you_search_sync, query=q, count=10, freshness="week")
    except Exception as e:  # noqa: BLE001
        logger.warning("You.com YDC search failed (continuing with corpus only): %s", e)
        return []
    max_sn = int(os.environ.get("PRISM_YOU_MAX_SNIPPETS", "5"))
    rows = ydc_snippets_from_payload(payload, max_items=max(1, min(max_sn, 10)))
    out: list[RetrievedChunk] = []
    for i, row in enumerate(rows):
        title = (row.get("title") or "untitled")[:240]
        kind = row.get("kind") or "web"
        url = row.get("url")
        body_txt = (row.get("body") or "").strip()
        body = f"[You.com {kind}] {title}\n{body_txt}"[:2000]
        uid_src = url if url else f"you:{ticker}:{i}:{title}"
        uid = uuid.uuid5(uuid.NAMESPACE_URL, str(uid_src)[:500])
        out.append(
            RetrievedChunk(
                index=i,
                chunk_id=uid,
                body=body,
                doc_title=f"You.com | {title}"[:220],
                score=0.95 - i * 0.02,
                is_external=True,
            )
        )
    return out


async def run_research(
    session: AsyncSession,
    *,
    tenant_id: str,
    ticker: str,
    question: str,
) -> tuple[dict[str, Any], list[RetrievedChunk], int]:
    """Return (hop_payload, chunks, duration_ms)."""
    t0 = time.perf_counter()
    qv = embed_texts([question])[0]
    if (
        os.environ.get("PRISM_QUERY_EMBED_OLLAMA", "").lower() in ("1", "true", "yes")
        and embeddings_enabled()
    ):
        try:
            ov = await ollama_embed_query(question)
            if len(ov) == 384:
                qv = ov
            else:
                logger.warning(
                    "Ollama embedding dim=%s != 384; using embed_texts for DB alignment",
                    len(ov),
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("ollama embed failed, using embed_texts: %s", e)

    tr = TenantRetriever(session, tenant_id=tenant_id, ticker=ticker)
    vec_chunks = await tr.search(qv, question=question, pool=28, top_k=12)
    you_chunks = await _you_com_chunks(ticker=ticker, question=question)
    chunks = _renumber_chunks(you_chunks + vec_chunks)
    ms = int((time.perf_counter() - t0) * 1000)
    top_scores = [round(c.score, 5) for c in chunks[:5]]
    hop_payload = {
        "agent": "Research",
        "intent": "vector_retrieval_plus_you_com",
        "chunk_count": len(chunks),
        "vector_chunk_count": len(vec_chunks),
        "you_com_chunk_count": len(you_chunks),
        "you_com_used": bool(you_chunks),
        "top_scores": top_scores,
        "query_preview": question[:200],
    }
    logger.info(
        "Research: tenant=%s ticker=%s chunks=%s (you=%s vec=%s) top_scores=%s",
        tenant_id,
        ticker,
        len(chunks),
        len(you_chunks),
        len(vec_chunks),
        top_scores,
    )
    return hop_payload, chunks, ms


def chunks_to_research_dict(chunks: list[RetrievedChunk], question: str) -> dict[str, Any]:
    return {
        "chunks": [
            {
                "index": c.index,
                "chunk_id": str(c.chunk_id),
                "body": c.body,
                "title": c.doc_title,
                "score": c.score,
            }
            for c in chunks
        ],
        "query": question,
    }
