from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from prism_api.db import SessionLocal, get_db
from prism_api.models import (
    AnalystFeedback,
    Chunk,
    Document,
    EvalRun,
    EvidenceAccessRequest,
    Run,
    TenantLlmProfile,
    TenantMember,
)
from prism_api.services.eval_scenarios import run_static_eval_on_outputs
from prism_api.services.ingest_service import ingest_documents, ingest_pdf_document
from prism_api.integrations.veris_mount import mount_veris_fastapi_mcp
from prism_api.integrations.you_com import you_search_sync
from prism_api.services.llm_runtime import load_llm_runtime
from prism_api.services.pdf_ingest import pdf_to_text
from prism_api.services.pii_scrub import scrub_text
from prism_api.services.rbac import require_tenant_role
from prism_api.services.run_service import execute_prism_run, load_run_bundle, stream_prism_run

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Prism API", version="0.1.0")

_cors_raw = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
# With allow_credentials=True, browsers reject Access-Control-Allow-Headers: * on preflight.
_cors_headers = [
    "Accept",
    "Accept-Language",
    "Content-Type",
    "X-Prism-Tenant",
    "X-Prism-Principal",
    "Authorization",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=_cors_headers,
)


@app.exception_handler(Exception)
async def _prism_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Return JSON (not opaque HTML) so clients and the Next proxy can show `detail`."""
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    logger.exception("%s %s", request.method, request.url.path)
    if os.environ.get("PRISM_DEBUG_ERRORS", "").lower() in ("1", "true", "yes"):
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "exc_type": type(exc).__name__},
        )
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Internal server error. If this is a DB schema mismatch, run migrations or "
                "`docker compose down -v` then `docker compose up -d` for a fresh DB. "
                "Set PRISM_DEBUG_ERRORS=1 for the exception message."
            )
        },
    )


def _tenant_id(x_prism_tenant: str | None, fallback: str | None) -> str:
    tid = (x_prism_tenant or fallback or "default").strip()
    if not tid or len(tid) > 64:
        raise HTTPException(400, "invalid tenant id")
    return tid[:64]


def _principal(x_prism_principal: str | None) -> str | None:
    if not x_prism_principal:
        return None
    p = x_prism_principal.strip()
    return p[:256] if p else None


class IngestBody(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    transcript: str | None = None
    filing_excerpt: str | None = None
    internal_notes: str | None = None
    tenant_id: str | None = Field(None, max_length=64)


@app.post("/v1/ingest")
async def ingest(
    body: IngestBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, body.tenant_id)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="analyst")
    ids = await ingest_documents(
        db,
        tenant_id=tid,
        ticker=body.ticker,
        transcript=body.transcript,
        filing_excerpt=body.filing_excerpt,
        internal_notes=body.internal_notes,
    )
    return {"ok": True, "tenant_id": tid, "document_ids": ids}


@app.post("/v1/ingest/pdf")
async def ingest_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    ticker: str = Query(..., min_length=1, max_length=16),
    title: str | None = Query(None, max_length=512),
    tenant_id: str | None = Query(None, max_length=64),
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, tenant_id)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="analyst")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")
    try:
        text = pdf_to_text(raw)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    if not text.strip():
        raise HTTPException(400, "no text extracted from PDF")
    doc_title = (title or file.filename or f"{ticker.upper()} filing").strip()[:512]
    doc_id = await ingest_pdf_document(
        db, tenant_id=tid, ticker=ticker, title=doc_title, body=text
    )
    return {"ok": True, "tenant_id": tid, "document_id": str(doc_id)}


@app.get("/v1/tenants/{tenant_id}/corpus")
async def list_tenant_corpus(
    tenant_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    ticker: str = Query(..., min_length=1, max_length=16),
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    """Documents (and chunk counts) the retriever can use for this tenant + ticker."""
    tid = _tenant_id(x_prism_tenant, tenant_id)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="viewer")
    t_up = ticker.strip().upper()
    stmt = (
        select(
            Document.id,
            Document.title,
            Document.source_kind,
            Document.created_at,
            func.count(Chunk.id).label("chunk_count"),
        )
        .select_from(Document)
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .where(Document.tenant_id == tid, Document.ticker == t_up)
        .group_by(Document.id, Document.title, Document.source_kind, Document.created_at)
        .order_by(Document.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return {
        "tenant_id": tid,
        "ticker": t_up,
        "documents": [
            {
                "id": str(r[0]),
                "title": r[1],
                "source_kind": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "chunk_count": int(r[4] or 0),
            }
            for r in rows
        ],
    }


class CreateRunBody(BaseModel):
    ticker: str
    question: str
    include_mcp: bool = True
    tenant_id: str | None = Field(None, max_length=64)


@app.post("/v1/runs")
async def create_run(
    body: CreateRunBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, body.tenant_id)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="analyst")
    run = Run(
        tenant_id=tid,
        ticker=body.ticker.strip().upper(),
        question=body.question.strip(),
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return {"run_id": str(run.id), "tenant_id": tid, "status": run.status}


@app.post("/v1/runs/{run_id}/execute")
async def execute_run(
    run_id: uuid.UUID,
    background: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_mcp: bool = Query(True),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    """Run pipeline in background (non-streaming clients)."""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    await require_tenant_role(
        db, tenant_id=run.tenant_id, principal=_principal(x_prism_principal), min_role="analyst"
    )

    ticker, question = run.ticker, run.question

    async def job() -> None:
        async with SessionLocal() as s:
            await execute_prism_run(
                s,
                run_id=run_id,
                ticker=ticker,
                question=question,
                include_mcp=include_mcp,
            )

    background.add_task(job)
    return {"ok": True, "run_id": str(run_id)}


@app.get("/v1/runs/{run_id}/stream")
async def stream_run(
    run_id: uuid.UUID,
    include_mcp: bool = Query(True),
    tenant: str = Query("default"),
    principal: str | None = Query(
        None,
        max_length=256,
        description="Optional principal for RBAC (EventSource cannot send custom headers).",
    ),
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, tenant)
    principal_eff = _principal(x_prism_principal) or _principal(principal)

    async def gen():
        async with SessionLocal() as db:
            await require_tenant_role(db, tenant_id=tid, principal=principal_eff, min_role="analyst")
            run = await db.get(Run, run_id)
            if not run or run.tenant_id != tid:
                yield f"data: {json.dumps({'event': 'error', 'message': 'run not found'})}\n\n"
                return
            if run.status == "completed":
                bundle = await load_run_bundle(db, run_id)
                yield f"data: {json.dumps({'event': 'cached', 'bundle': bundle})}\n\n"
                return
            try:
                async for line in stream_prism_run(
                    db,
                    run_id=run_id,
                    ticker=run.ticker,
                    question=run.question,
                    include_mcp=include_mcp,
                ):
                    yield line
                bundle = await load_run_bundle(db, run_id)
                yield f"data: {json.dumps({'event': 'bundle', 'bundle': bundle})}\n\n"
            except Exception as e:  # noqa: BLE001
                logger.exception("stream failed for run %s", run_id)
                async with SessionLocal() as db2:
                    r2 = await db2.get(Run, run_id)
                    if r2 and r2.status == "running":
                        r2.status = "failed"
                        await db2.commit()
                yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/v1/runs/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, None)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="viewer")
    bundle = await load_run_bundle(db, run_id)
    if not bundle or bundle.get("run", {}).get("tenant_id") != tid:
        raise HTTPException(404, "run not found")
    return bundle


class TenantMemberUpsert(BaseModel):
    principal: str = Field(..., min_length=1, max_length=256)
    role: str = Field(..., min_length=3, max_length=32)


class AnalystFeedbackBody(BaseModel):
    thumbs: int | None = Field(None, ge=-1, le=1)
    note: str | None = Field(None, max_length=16000)
    edited_thesis: dict[str, Any] | None = None


class EvidenceAccessBody(BaseModel):
    chunk_id: uuid.UUID | None = None
    subject_tenant_id: str | None = Field(None, max_length=64)
    subject_ticker: str | None = Field(None, max_length=32)
    request_note: str | None = Field(None, max_length=8000)


@app.get("/v1/tenants/{tenant_id}/members")
async def list_tenant_members(
    tenant_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = tenant_id.strip()[:64]
    if not tid:
        raise HTTPException(400, "invalid tenant_id")
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="viewer")
    rows = (await db.execute(select(TenantMember).where(TenantMember.tenant_id == tid))).scalars().all()
    return {"tenant_id": tid, "members": [{"principal": r.principal, "role": r.role} for r in rows]}


@app.put("/v1/tenants/{tenant_id}/members")
async def upsert_tenant_member(
    tenant_id: str,
    body: TenantMemberUpsert,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = tenant_id.strip()[:64]
    if not tid:
        raise HTTPException(400, "invalid tenant_id")
    if body.role not in ("viewer", "analyst", "admin"):
        raise HTTPException(400, "role must be viewer, analyst, or admin")
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="admin")
    p = body.principal.strip()[:256]
    if not p:
        raise HTTPException(400, "invalid principal")
    res = await db.execute(
        select(TenantMember).where(TenantMember.tenant_id == tid, TenantMember.principal == p)
    )
    row = res.scalar_one_or_none()
    if row is None:
        db.add(TenantMember(tenant_id=tid, principal=p, role=body.role))
    else:
        row.role = body.role
    await db.commit()
    return {"tenant_id": tid, "principal": p, "role": body.role, "ok": True}


@app.post("/v1/runs/{run_id}/feedback")
async def post_run_feedback(
    run_id: uuid.UUID,
    body: AnalystFeedbackBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, None)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="analyst")
    run = await db.get(Run, run_id)
    if not run or run.tenant_id != tid:
        raise HTTPException(404, "run not found")
    scrubbed = scrub_text(body.note or "") if body.note else None
    fb = AnalystFeedback(
        tenant_id=tid,
        run_id=run_id,
        thumbs=body.thumbs,
        note=body.note,
        scrubbed_note=scrubbed,
        edited_thesis=body.edited_thesis,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return {"ok": True, "feedback_id": str(fb.id)}


@app.post("/v1/evidence-access-requests")
async def create_evidence_access_request(
    body: EvidenceAccessBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, None)
    p = _principal(x_prism_principal)
    if not p:
        raise HTTPException(400, "X-Prism-Principal required for evidence access request")
    await require_tenant_role(db, tenant_id=tid, principal=p, min_role="analyst")
    st = (body.subject_tenant_id or "").strip()[:64] or None
    stk = (body.subject_ticker or "").strip().upper()[:32] or None
    note = (body.request_note or "").strip()[:8000] or None
    req = EvidenceAccessRequest(
        tenant_id=tid,
        chunk_id=body.chunk_id,
        requester=p,
        subject_tenant_id=st,
        subject_ticker=stk,
        request_note=note,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return {
        "ok": True,
        "request_id": str(req.id),
        "status": req.status,
        "subject_tenant_id": req.subject_tenant_id,
        "subject_ticker": req.subject_ticker,
    }


@app.post("/v1/runs/{source_run_id}/replay")
async def replay_run(
    source_run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, None)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="analyst")
    src = await db.get(Run, source_run_id)
    if not src or src.tenant_id != tid:
        raise HTTPException(404, "run not found")
    new_run = Run(
        tenant_id=tid,
        ticker=src.ticker,
        question=src.question,
        status="pending",
        replay_of=source_run_id,
    )
    db.add(new_run)
    await db.commit()
    await db.refresh(new_run)
    return {
        "run_id": str(new_run.id),
        "tenant_id": tid,
        "replay_of": str(source_run_id),
        "status": new_run.status,
    }


class EvalBody(BaseModel):
    run_id: uuid.UUID


class TenantLlmProfileUpsert(BaseModel):
    """Secrets are never stored: use api_key_env / google_api_key_env pointing at process env."""

    model_id: str = Field(..., min_length=2, max_length=512)
    openai_api_base: str | None = Field(None, max_length=1024)
    ollama_api_base: str | None = Field(None, max_length=1024)
    api_key_env: str | None = Field(None, max_length=128)
    google_api_key_env: str | None = Field(None, max_length=128)


@app.put("/v1/tenants/{tenant_id}/llm-profile")
async def upsert_tenant_llm_profile(
    tenant_id: str,
    body: TenantLlmProfileUpsert,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = tenant_id.strip()[:64]
    if not tid or len(tid) > 64:
        raise HTTPException(400, "invalid tenant_id")
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="admin")
    row = await db.get(TenantLlmProfile, tid)
    if row is None:
        row = TenantLlmProfile(tenant_id=tid, model_id=body.model_id.strip())
        db.add(row)
    else:
        row.model_id = body.model_id.strip()
    row.openai_api_base = body.openai_api_base.strip() if body.openai_api_base else None
    row.ollama_api_base = body.ollama_api_base.strip() if body.ollama_api_base else None
    row.api_key_env = body.api_key_env.strip() if body.api_key_env else None
    row.google_api_key_env = body.google_api_key_env.strip() if body.google_api_key_env else None
    row.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return {"tenant_id": tid, "ok": True}


@app.get("/v1/tenants/{tenant_id}/llm-profile")
async def get_tenant_llm_profile(
    tenant_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = tenant_id.strip()[:64]
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="viewer")
    row = await db.get(TenantLlmProfile, tid)
    if row is None:
        return {"tenant_id": tid, "configured": False}
    return {
        "tenant_id": tid,
        "configured": True,
        "model_id": row.model_id,
        "openai_api_base": row.openai_api_base,
        "ollama_api_base": row.ollama_api_base,
        "api_key_env": row.api_key_env,
        "google_api_key_env": row.google_api_key_env,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@app.post("/v1/eval/regression")
async def eval_regression(
    body: EvalBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    tid = _tenant_id(x_prism_tenant, None)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="analyst")
    run = await db.get(Run, body.run_id)
    if not run or run.tenant_id != tid:
        raise HTTPException(404, "run not found")
    if run.status != "completed":
        raise HTTPException(400, f"run not completed (status={run.status})")
    if run.thesis_json is None:
        raise HTTPException(400, "run completed but thesis_json is null")
    thesis_blob = json.dumps(run.thesis_json)
    bundle = await load_run_bundle(db, body.run_id)
    cx = json.dumps(bundle.get("contradictions", []))
    report = run_static_eval_on_outputs(thesis_blob, cx)
    er = EvalRun(passed=report["passed"], failed=report["failed"], scenarios=report["scenarios"])
    db.add(er)
    await db.commit()
    await db.refresh(er)
    return {"eval_run_id": str(er.id), **report}


@app.get("/health")
async def health():
    return {"status": "ok"}


def _ollama_api_reachable(base: str) -> bool:
    """Best-effort TCP/HTTP check (short timeout; safe for /integrations)."""
    url = f"{base.rstrip('/')}/api/tags"
    try:
        r = httpx.get(url, timeout=0.75)
        return r.status_code == 200
    except Exception:
        return False


@app.get("/v1/integrations")
async def integrations_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant: str = Query("default", max_length=64),
):
    """Which sponsor integrations are configured for this tenant (no secrets exposed)."""
    tid = (tenant or "default").strip()[:64] or "default"
    rt = await load_llm_runtime(db, tid)
    model = rt.model_id
    uses_litellm = "/" in model and not model.startswith("gemini-")
    ollama_model = model.startswith("ollama/") or model.startswith("ollama_chat/")
    ollama_base = (
        (rt.ollama_api_base or os.environ.get("PRISM_OLLAMA_BASE") or "http://127.0.0.1:11434").strip()
        if ollama_model
        else None
    )
    ollama_reachable = _ollama_api_reachable(ollama_base) if ollama_base else None
    prov = (os.environ.get("PRISM_LLM_PROVIDER") or "").strip().lower() or "auto"
    model_warn: str | None = None
    api_key = (os.environ.get("BASETEN_API_KEY") or "").strip()
    if model.startswith("openai/") and api_key:
        slug = model.split("/", 1)[1] if "/" in model else ""
        if slug == api_key:
            model_warn = (
                "PRISM_ADK_MODEL is set to your Baseten API key. Use BASETEN_API_KEY for authentication "
                "and PRISM_ADK_MODEL=openai/<model_id> where <model_id> comes from "
                "https://inference.baseten.co/v1/models (not the key)."
            )
    if model_warn is None and "YOUR_BASETEN_MODEL_SLUG" in model:
        model_warn = (
            "PRISM_ADK_MODEL still contains YOUR_BASETEN_MODEL_SLUG; replace it with a real slug from "
            "curl -s https://inference.baseten.co/v1/models -H \"Authorization: Api-Key $BASETEN_API_KEY\"."
        )
    # How chat reaches Baseten: LiteLLM speaks OpenAI-compatible JSON to OPENAI_API_BASE (set from BASETEN_OPENAI_BASE).
    chat_via = (
        "ollama_native_http"
        if ollama_model
        else ("litellm_openai_compat" if uses_litellm else "google_gemini_sdk")
    )
    return {
        "tenant_id": tid,
        "llm": {
            "provider": prov,
            "baseten_only": prov == "baseten",
            "model_id": model,
            "model_config_warning": model_warn,
            "chat_via": chat_via,
            "route": "litellm" if uses_litellm else "gemini",
            "openai_credentials_resolved": bool((rt.openai_api_key or "").strip()),
            "openai_compatible_local_ready": bool((rt.openai_api_base or "").strip())
            and model.startswith("openai/")
            and not (rt.openai_api_base or "").startswith("https://inference.baseten.co"),
            "ollama": ollama_model,
            "ollama_base": ollama_base,
            "ollama_reachable": ollama_reachable,
            "ollama_hint": (
                "Install and start Ollama, then: ollama pull <name> where model_id is "
                "ollama/<name>. Or set ollama_api_base on the tenant LLM profile."
                if ollama_model and ollama_reachable is False
                else None
            ),
            "google_gemini_configured": bool((rt.google_api_key or "").strip()),
        },
        "you_com": {"search_configured": bool(os.environ.get("YOU_API_KEY", "").strip())},
        "veris": {
            "fastapi_mcp_mount": os.environ.get("ENABLE_VERIS_MCP", "").lower() in ("1", "true", "yes"),
            "template": "See .veris/veris.yaml and https://docs.veris.ai/quickstart",
        },
    }


@app.get("/v1/you/preview")
async def you_preview(q: str = Query(..., min_length=2, description="Search query for You.com YDC")):
    """Smoke-test You.com Search API (same backend as MCP get_news_digest)."""
    try:
        return you_search_sync(query=q, count=8)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"You.com request failed: {e}") from e


class VerisChatBody(BaseModel):
    message: str


def _parse_ticker_from_veris_message(msg: str) -> str:
    m = re.search(r"(?i)\bTICKER:\s*([A-Za-z0-9.-]{1,16})\b", msg)
    if m:
        return m.group(1).upper().strip()
    return os.environ.get("VERIS_DEFAULT_TICKER", "DEMO").strip().upper()[:16]


@app.post("/v1/veris/chat")
async def veris_chat(
    body: VerisChatBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_prism_tenant: str | None = Header(None, alias="X-Prism-Tenant"),
    x_prism_principal: str | None = Header(None, alias="X-Prism-Principal"),
):
    """HTTP contract for Veris simulated user → one full Prism run → thesis narrative."""
    tid = _tenant_id(x_prism_tenant, None)
    await require_tenant_role(db, tenant_id=tid, principal=_principal(x_prism_principal), min_role="analyst")
    ticker = _parse_ticker_from_veris_message(body.message)
    question = body.message.strip()
    run = Run(tenant_id=tid, ticker=ticker, question=question, status="pending")
    db.add(run)
    await db.commit()
    await db.refresh(run)
    await execute_prism_run(
        db,
        run_id=run.id,
        ticker=ticker,
        question=question,
        include_mcp=True,
    )
    bundle = await load_run_bundle(db, run.id)
    thesis = bundle.get("run", {}).get("thesis_json") or {}
    narrative = thesis.get("narrative") or json.dumps(thesis)[:8000]
    return {"response": narrative, "run_id": str(run.id), "ticker": ticker, "tenant_id": tid}


mount_veris_fastapi_mcp(app)


def app_main() -> None:
    import uvicorn

    uvicorn.run(
        "prism_api.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )
