"""Tenant-scoped chunk retrieval: vector similarity + optional CrossEncoder rerank."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prism_api.services.embeddings import embeddings_enabled


def _maybe_rerank(
    query: str,
    scored: list[tuple[float, str, uuid.UUID, str, int]],
) -> list[tuple[float, str, uuid.UUID, str, int]]:
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


@dataclass(frozen=True)
class RetrievedChunk:
    index: int
    chunk_id: uuid.UUID
    body: str
    doc_title: str
    score: float
    is_external: bool = False  # True for You.com etc.: not a row in `chunks`, do not FK `citations.chunk_id`


class TenantRetriever:
    """Hybrid search aligned with `prism_api.services.retrieve` (384-d pgvector)."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, ticker: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.ticker = ticker.upper()

    async def search(
        self,
        query_embedding: Sequence[float],
        *,
        question: str,
        pool: int = 24,
        top_k: int = 12,
    ) -> list[RetrievedChunk]:
        t_up = self.ticker
        vec_lit = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"

        if embeddings_enabled() and len(query_embedding) == 384:
            sql = text(
                """
                SELECT c.body, c.id::text, d.title,
                       (c.embedding <=> CAST(:qv AS vector)) AS dist,
                       c.chunk_index
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.tenant_id = :tid AND d.ticker = :tick AND c.embedding IS NOT NULL
                ORDER BY dist
                LIMIT :lim
                """
            )
            rows = (
                await self.session.execute(
                    sql, {"qv": vec_lit, "tid": self.tenant_id, "tick": t_up, "lim": pool}
                )
            ).all()
            scored: list[tuple[float, str, uuid.UUID, str, int]] = []
            for body, cid, title, dist, cidx in rows:
                scored.append(
                    (1.0 / (1.0 + float(dist)), body, uuid.UUID(cid), title or "", int(cidx or 0))
                )
            scored = _maybe_rerank(question, scored)
        else:
            from sqlalchemy import Select, select

            from prism_api.models import Chunk, Document

            q_words = {w.lower() for w in question.split() if len(w) > 2}
            if not q_words:
                q_words = {"revenue", "margin", "growth", "risk"}
            stmt: Select[tuple[Chunk, Document]] = (
                select(Chunk, Document)
                .join(Document, Chunk.document_id == Document.id)
                .where(Document.tenant_id == self.tenant_id, Document.ticker == t_up)
                .order_by(Chunk.chunk_index)
                .limit(pool)
            )
            rows2 = (await self.session.execute(stmt)).all()
            scored = []
            for ch, doc in rows2:
                low = ch.body.lower()
                score = float(sum(1 for w in q_words if w in low))
                scored.append((score, ch.body, ch.id, doc.title or "", ch.chunk_index))
            scored.sort(key=lambda x: -x[0])
            scored = _maybe_rerank(question, scored)

        out: list[RetrievedChunk] = []
        for i, (sc, body, cid, title, _cidx) in enumerate(scored[:top_k]):
            out.append(
                RetrievedChunk(index=i, chunk_id=cid, body=body, doc_title=title, score=float(sc))
            )
        return out
