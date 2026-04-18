"""Chunk embeddings (384-dim pgvector): optional sentence-transformers, else deterministic hash fallback."""

from __future__ import annotations

import hashlib
import math
import os
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prism_api.models import Chunk

_DIM = 384


def _hash_embedding(text: str) -> list[float]:
    """Deterministic 384-d unit vector (no ML deps) for dev / CI."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    i = 0
    while len(out) < _DIM:
        b = h[i % len(h)]
        out.append((b / 127.5) - 1.0)
        i += 1
    norm = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / norm for x in out]


def _sentence_transformer_encode(texts: Sequence[str]) -> list[list[float]]:
    from sentence_transformers import SentenceTransformer

    model_name = os.environ.get("PRISM_EMBED_MODEL", "all-MiniLM-L6-v2")
    m = SentenceTransformer(model_name)
    vecs = m.encode(list(texts), normalize_embeddings=True)
    return [list(map(float, v)) for v in vecs]


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if os.environ.get("PRISM_USE_SENTENCE_TRANSFORMERS", "").lower() in ("1", "true", "yes"):
        try:
            return _sentence_transformer_encode(texts)
        except Exception:  # noqa: BLE001
            pass
    return [_hash_embedding(t) for t in texts]


def embeddings_enabled() -> bool:
    return os.environ.get("PRISM_USE_EMBEDDINGS", "").lower() in ("1", "true", "yes")


async def embed_chunks_for_documents(session: AsyncSession, document_ids: list[uuid.UUID]) -> None:
    if not embeddings_enabled() or not document_ids:
        return
    res = await session.execute(
        select(Chunk).where(Chunk.document_id.in_(document_ids), Chunk.embedding.is_(None))
    )
    chunks = res.scalars().all()
    if not chunks:
        return
    bodies = [c.body for c in chunks]
    vectors = embed_texts(bodies)
    for ch, vec in zip(chunks, vectors, strict=True):
        ch.embedding = vec
    await session.flush()
