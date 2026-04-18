from __future__ import annotations

import os
import uuid
from typing import Any

from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from prism_api.models import Chunk, Document
from prism_api.services.embeddings import embed_texts, embeddings_enabled


def _maybe_rerank(query: str, scored: list[tuple[float, str, uuid.UUID, str]]) -> list[tuple[float, str, uuid.UUID, str]]:
    if os.environ.get("PRISM_USE_RERANKER", "").lower() not in ("1", "true", "yes"):
        return scored
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        return scored
    if len(scored) <= 1:
        return scored
    model_name = os.environ.get("PRISM_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    ce = CrossEncoder(model_name)
    pairs = [(query, s[1]) for s in scored]
    scores = ce.predict(pairs)
    merged = list(zip(scores, scored, strict=True))
    merged.sort(key=lambda x: -float(x[0]))
    return [m[1] for m in merged]


async def fetch_corpus_excerpt(
    session: AsyncSession,
    ticker: str,
    question: str,
    *,
    tenant_id: str = "default",
    limit: int = 10,
) -> str:
    """Hybrid retrieval: pgvector cosine when embeddings on, else keyword overlap."""
    t_up = ticker.upper()
    q_words = {w.lower() for w in question.split() if len(w) > 2}
    if not q_words:
        q_words = {"revenue", "margin", "growth", "risk"}

    if embeddings_enabled():
        qv = embed_texts([question])[0]
        vec_lit = "[" + ",".join(str(float(x)) for x in qv) + "]"
        sql = text(
            """
            SELECT c.body, c.id::text, d.title,
                   (c.embedding <=> CAST(:qv AS vector)) AS dist
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.tenant_id = :tid AND d.ticker = :tick AND c.embedding IS NOT NULL
            ORDER BY dist
            LIMIT 40
            """
        )
        rows = (await session.execute(sql, {"qv": vec_lit, "tid": tenant_id, "tick": t_up})).all()
        if rows:
            scored: list[tuple[float, str, uuid.UUID, str]] = []
            for body, cid, title, dist in rows:
                scored.append((1.0 / (1.0 + float(dist)), body, uuid.UUID(cid), title))
            scored = _maybe_rerank(question, scored)
            top = scored[:limit]
            parts = []
            for score, body, chunk_id, title in top:
                parts.append(f"[score={score:.4f} doc={title} chunk_id={chunk_id}]\n{body}")
            return "\n\n---\n\n".join(parts)

    stmt: Select[tuple[Chunk, Document]] = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.tenant_id == tenant_id, Document.ticker == t_up)
        .order_by(Chunk.chunk_index)
        .limit(40)
    )
    rows = (await session.execute(stmt)).all()
    scored2: list[tuple[float, str, uuid.UUID, str]] = []
    for ch, doc in rows:
        low = ch.body.lower()
        score = sum(1 for w in q_words if w in low)
        scored2.append((float(score), ch.body, ch.id, doc.title))

    scored2.sort(key=lambda x: -x[0])
    scored2 = _maybe_rerank(question, scored2)
    top2 = scored2[:limit]
    parts2 = []
    for score, body, chunk_id, title in top2:
        parts2.append(f"[score={score} doc={title} chunk_id={chunk_id}]\n{body}")
    return "\n\n---\n\n".join(parts2) if parts2 else "(no internal documents ingested for this ticker)"
