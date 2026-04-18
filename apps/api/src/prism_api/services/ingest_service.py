from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from prism_api.models import Chunk, Document
from prism_api.services.chunking import chunk_text
from prism_api.services.embeddings import embed_chunks_for_documents


async def ingest_documents(
    session: AsyncSession,
    *,
    tenant_id: str = "default",
    ticker: str,
    transcript: str | None = None,
    filing_excerpt: str | None = None,
    internal_notes: str | None = None,
) -> dict[str, list[str]]:
    """Insert documents + chunks for a ticker. Returns mapping kind -> document ids."""
    t = ticker.upper()
    created: dict[str, list[str]] = {}
    new_doc_ids: list[uuid.UUID] = []

    async def add_doc(kind: str, title: str, body: str) -> None:
        if not body.strip():
            return
        doc = Document(
            tenant_id=tenant_id,
            ticker=t,
            title=title,
            source_kind=kind,
            body=body.strip(),
        )
        session.add(doc)
        await session.flush()
        new_doc_ids.append(doc.id)
        for idx, ch in enumerate(chunk_text(body)):
            session.add(
                Chunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    body=ch,
                )
            )
        created.setdefault(kind, []).append(str(doc.id))

    await add_doc("earnings_transcript", f"{t} earnings call transcript", transcript or "")
    await add_doc("filing", f"{t} filing excerpt", filing_excerpt or "")
    await add_doc("internal_note", f"{t} internal notes", internal_notes or "")
    await embed_chunks_for_documents(session, new_doc_ids)
    await session.commit()
    return created


async def ingest_pdf_document(
    session: AsyncSession,
    *,
    tenant_id: str,
    ticker: str,
    title: str,
    body: str,
) -> uuid.UUID:
    """Store a single PDF-derived filing as `pdf_filing` with chunks + optional embeddings."""
    t = ticker.upper()
    doc = Document(
        tenant_id=tenant_id,
        ticker=t,
        title=title,
        source_kind="pdf_filing",
        body=body.strip(),
    )
    session.add(doc)
    await session.flush()
    for idx, ch in enumerate(chunk_text(body)):
        session.add(Chunk(document_id=doc.id, chunk_index=idx, body=ch))
    await embed_chunks_for_documents(session, [doc.id])
    await session.commit()
    await session.refresh(doc)
    return doc.id
