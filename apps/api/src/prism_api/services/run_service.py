from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any, AsyncIterator

from google.adk.runners import InMemoryRunner
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adk_prism.pipeline import build_root_agent
from adk_prism.schemas import ContradictionPayload, ThesisPayload, safe_parse
from backend.agents.pipeline import execute_fast_pipeline, stream_fast_pipeline
from prism_api.models import Contradiction, Hop, MatrixRow, Run
from prism_api.services.llm_runtime import load_llm_runtime, use_llm_runtime
from prism_api.services.local_learning_signals import compute_local_learning_signals
from prism_api.services.quality_gate import evaluate_thesis_quality
from prism_api.services.retrieve import fetch_corpus_excerpt

logger = logging.getLogger(__name__)

# ADK/LiteLLM read process env; serialize LLM calls so tenant env overlays never race.
_adk_llm_lock = asyncio.Lock()


def _json_from_state(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("```"):
            lines = s.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            s = "\n".join(lines).strip()
        return json.loads(s)
    return json.loads(str(val))


def _serialize_event(ev: Any) -> dict[str, Any]:
    try:
        name = ev.__class__.__name__
        out: dict[str, Any] = {"type": name}
        if hasattr(ev, "model_dump"):
            out["data"] = ev.model_dump(mode="json", exclude_none=True)
        elif hasattr(ev, "__dict__"):
            out["data"] = str(ev.__dict__)[:2000]
        return out
    except Exception:  # noqa: BLE001
        return {"type": "unknown", "data": str(ev)[:500]}


def _adk_event_one_liner(ev: Any) -> str:
    """Short text for logs/SSE (ADK event shapes vary by version)."""
    try:
        cls = ev.__class__.__name__
        if hasattr(ev, "model_dump"):
            d = ev.model_dump(mode="json", exclude_none=True)
            if isinstance(d, dict):
                for key in ("agent", "author", "name", "invocation_id", "id"):
                    v = d.get(key)
                    if v is not None and str(v).strip():
                        return f"{cls} · {key}={v!s}"[:240]
        return cls
    except Exception:  # noqa: BLE001
        return ev.__class__.__name__


async def execute_prism_run(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    ticker: str,
    question: str,
    include_mcp: bool = True,
) -> None:
    """Blocking pipeline execution (used by background task + non-SSE)."""
    t0 = time.perf_counter()
    run = await db.get(Run, run_id)
    if not run:
        return
    run.status = "running"
    await db.commit()

    use_adk = os.environ.get("PRISM_PIPELINE", "fast").lower() == "adk"

    async with _adk_llm_lock:
        rt = await load_llm_runtime(db, run.tenant_id)
        with use_llm_runtime(rt):
            if not use_adk:
                await execute_fast_pipeline(
                    db,
                    run_id=run_id,
                    ticker=ticker,
                    question=question,
                    model_id=rt.model_id,
                )
            else:
                corpus = await fetch_corpus_excerpt(db, ticker, question, tenant_id=run.tenant_id)
                user_blob = (
                    f"INTERNAL_CORPUS:\n{corpus}\n\nTicker: {ticker.upper()}\nQUESTION:\n{question}\n"
                )
                agent = build_root_agent(include_mcp=include_mcp, llm_model=rt.model_id)
                runner = InMemoryRunner(agent=agent, app_name="prism")
                user_id = "prism_user"
                session_id = str(run_id)

                sess = await runner.session_service.get_session(
                    app_name=runner.app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                if not sess:
                    await runner.session_service.create_session(
                        app_name=runner.app_name,
                        user_id=user_id,
                        session_id=session_id,
                    )

                new_message = types.UserContent(parts=[types.Part(text=user_blob)])
                async for _ev in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=new_message,
                ):
                    pass

                session = await runner.session_service.get_session(
                    app_name=runner.app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                state = getattr(session, "state", None) or {}

                keys = ("research_json", "reasoning_json", "contradiction_json", "thesis_json")
                parsed: dict[str, Any] = {}
                for k in keys:
                    if k not in state:
                        continue
                    try:
                        parsed[k] = _json_from_state(state[k])
                    except Exception as e:  # noqa: BLE001
                        logger.warning("parse %s: %s", k, e)
                        parsed[k] = {"raw": str(state[k])[:8000]}

                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                per_ms = max(elapsed_ms // 4, 1)

                for k in keys:
                    if k not in parsed:
                        continue
                    hop = Hop(
                        run_id=run_id,
                        agent=k.replace("_json", "").title(),
                        intent=k,
                        payload=parsed[k] if isinstance(parsed[k], dict) else {"value": parsed[k]},
                        duration_ms=per_ms,
                    )
                    db.add(hop)

                thesis_data = parsed.get("thesis_json") or {}
                try:
                    thesis_model = safe_parse(ThesisPayload, thesis_data)
                except Exception:  # noqa: BLE001
                    thesis_model = ThesisPayload(
                        narrative=json.dumps(thesis_data)[:4000] if thesis_data else "",
                        matrix_rows=[],
                    )
                run.thesis_json = thesis_model.model_dump()
                for order, row in enumerate(thesis_model.matrix_rows):
                    db.add(
                        MatrixRow(
                            run_id=run_id,
                            theme=row.theme,
                            summary=row.summary,
                            confidence=row.confidence,
                            evidence=row.evidence,
                            citation_ids=list(row.citation_labels),
                            row_order=order,
                        )
                    )

                try:
                    cx = safe_parse(ContradictionPayload, parsed.get("contradiction_json") or {})
                except Exception:  # noqa: BLE001
                    cx = ContradictionPayload(contradictions=[])
                for c in cx.contradictions:
                    db.add(
                        Contradiction(
                            run_id=run_id,
                            tension_type=c.tension_type,
                            description=c.description,
                            side_a_citation_ids=[c.side_a],
                            side_b_citation_ids=[c.side_b],
                        )
                    )

                qp, qrep = evaluate_thesis_quality(
                    thesis=run.thesis_json or {},
                    contradiction_count=len(cx.contradictions),
                )
                run.quality_passed = qp
                run.quality_report = qrep

                run.status = "completed"
                run.completed_at = datetime.now(UTC)
                await db.commit()
                await runner.close()


async def stream_prism_run(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    ticker: str,
    question: str,
    include_mcp: bool = True,
) -> AsyncIterator[str]:
    """SSE stream: status events + either fast pipeline hops or ADK events + final summary."""
    yield _sse({"event": "started", "run_id": str(run_id)})

    run = await db.get(Run, run_id)
    if not run:
        yield _sse({"event": "error", "message": "run not found"})
        return

    run.status = "running"
    await db.commit()
    yield _sse({"event": "status", "status": "running"})

    use_adk = os.environ.get("PRISM_PIPELINE", "fast").lower() == "adk"
    elapsed_ms = 0

    if use_adk:
        corpus = await fetch_corpus_excerpt(db, ticker, question, tenant_id=run.tenant_id)
        yield _sse({"event": "retrieval", "chars": len(corpus)})
        user_blob = (
            f"INTERNAL_CORPUS:\n{corpus}\n\nTicker: {ticker.upper()}\nQUESTION:\n{question}\n"
        )

    yield _sse(
        {
            "event": "phase",
            "phase": "llm_lock",
            "message": "Waiting for LLM lock (only one pipeline run uses the model at a time)",
        }
    )
    async with _adk_llm_lock:
        rt = await load_llm_runtime(db, run.tenant_id)
        logger.info("run %s: LLM model=%s include_mcp=%s pipeline=%s", run_id, rt.model_id, include_mcp, "adk" if use_adk else "fast")
        ready_msg = (
            "Tenant LLM resolved; Google ADK 4-agent chain (Research→Reasoning→Contradiction→Thesis)"
            if use_adk
            else "Tenant LLM resolved; fast pipeline: retrieval (no LLM) then 2 LLM calls (Analysis, Thesis)"
        )
        yield _sse({"event": "phase", "phase": "llm_ready", "model": rt.model_id, "message": ready_msg})
        with use_llm_runtime(rt):
            if not use_adk:
                async for ev in stream_fast_pipeline(
                    db,
                    run_id=run_id,
                    ticker=ticker,
                    question=question,
                    model_id=rt.model_id,
                ):
                    yield _sse(ev)
                    if ev.get("event") == "completed":
                        elapsed_ms = int(ev.get("elapsed_ms") or 0)
            else:
                agent = build_root_agent(include_mcp=include_mcp, llm_model=rt.model_id)
                runner = InMemoryRunner(agent=agent, app_name="prism")
                user_id = "prism_user"
                session_id = str(run_id)

                sess = await runner.session_service.get_session(
                    app_name=runner.app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                if not sess:
                    await runner.session_service.create_session(
                        app_name=runner.app_name,
                        user_id=user_id,
                        session_id=session_id,
                    )

                new_message = types.UserContent(parts=[types.Part(text=user_blob)])
                t0 = time.perf_counter()
                yield _sse(
                    {
                        "event": "phase",
                        "phase": "adk_started",
                        "message": "Calling Ollama/Gemini for each agent; first call is often the slowest (model load)",
                    }
                )
                last_heartbeat = t0
                n_adk = 0
                last_type = ""
                async for ev in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=new_message,
                ):
                    n_adk += 1
                    last_type = ev.__class__.__name__
                    now = time.perf_counter()
                    if now - last_heartbeat >= 12.0:
                        last_heartbeat = now
                        sec = int(now - t0)
                        line = f"{sec}s elapsed, {n_adk} ADK events, latest: {_adk_event_one_liner(ev)}"
                        logger.info("run %s heartbeat: %s", run_id, line)
                        yield _sse({"event": "phase", "phase": "adk_running", "message": line, "n_events": n_adk})
                    yield _sse({"event": "adk", "payload": _serialize_event(ev)})

                logger.info("run %s: ADK stream finished (%s events, last=%s)", run_id, n_adk, last_type)
                yield _sse(
                    {
                        "event": "phase",
                        "phase": "adk_done",
                        "message": f"Agent chain finished ({n_adk} events); parsing state and saving to Postgres",
                        "n_events": n_adk,
                    }
                )

                session = await runner.session_service.get_session(
                    app_name=runner.app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                state = getattr(session, "state", None) or {}
                keys = ("research_json", "reasoning_json", "contradiction_json", "thesis_json")
                present = [k for k in keys if k in state and state.get(k) not in (None, "", {})]
                logger.info(
                    "run %s: session state keys present: %s (missing thesis_json is OK until ThesisAgent finishes)",
                    run_id,
                    present or "none",
                )
                parsed: dict[str, Any] = {}
                for k in keys:
                    if k not in state:
                        continue
                    try:
                        parsed[k] = _json_from_state(state[k])
                    except Exception as e:  # noqa: BLE001
                        logger.warning("parse %s: %s", k, e)
                        parsed[k] = {"parse_error": str(e), "raw": str(state[k])[:4000]}

                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                per_ms = max(elapsed_ms // 4, 1)

                for k in keys:
                    if k not in parsed:
                        continue
                    hop = Hop(
                        run_id=run_id,
                        agent=k.replace("_json", "").title(),
                        intent=k,
                        payload=parsed[k] if isinstance(parsed[k], dict) else {"value": parsed[k]},
                        duration_ms=per_ms,
                    )
                    db.add(hop)

                thesis_data = parsed.get("thesis_json") or {}
                try:
                    thesis_model = safe_parse(ThesisPayload, thesis_data)
                except Exception:  # noqa: BLE001
                    thesis_model = ThesisPayload(
                        narrative=json.dumps(thesis_data)[:4000] if thesis_data else "",
                        matrix_rows=[],
                    )
                run.thesis_json = thesis_model.model_dump()
                for order, row in enumerate(thesis_model.matrix_rows):
                    db.add(
                        MatrixRow(
                            run_id=run_id,
                            theme=row.theme,
                            summary=row.summary,
                            confidence=row.confidence,
                            evidence=row.evidence,
                            citation_ids=list(row.citation_labels),
                            row_order=order,
                        )
                    )

                try:
                    cx = safe_parse(ContradictionPayload, parsed.get("contradiction_json") or {})
                except Exception:  # noqa: BLE001
                    cx = ContradictionPayload(contradictions=[])
                for c in cx.contradictions:
                    db.add(
                        Contradiction(
                            run_id=run_id,
                            tension_type=c.tension_type,
                            description=c.description,
                            side_a_citation_ids=[c.side_a],
                            side_b_citation_ids=[c.side_b],
                        )
                    )

                qp, qrep = evaluate_thesis_quality(
                    thesis=run.thesis_json or {},
                    contradiction_count=len(cx.contradictions),
                )
                run.quality_passed = qp
                run.quality_report = qrep

                yield _sse(
                    {
                        "event": "phase",
                        "phase": "db_commit",
                        "message": "Writing thesis, matrix, contradictions, quality gate",
                    }
                )
                run.status = "completed"
                run.completed_at = datetime.now(UTC)
                await db.commit()
                await runner.close()

        if use_adk:
            yield _sse({"event": "completed", "run_id": str(run_id), "elapsed_ms": elapsed_ms})


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj)}\n\n"


async def load_run_bundle(db: AsyncSession, run_id: uuid.UUID) -> dict[str, Any]:
    run = await db.get(Run, run_id)
    if not run:
        return {}
    hops = (
        (
            await db.execute(select(Hop).where(Hop.run_id == run_id).order_by(Hop.created_at))
        )
        .scalars()
        .all()
    )
    matrix = (
        (
            await db.execute(
                select(MatrixRow).where(MatrixRow.run_id == run_id).order_by(MatrixRow.row_order)
            )
        )
        .scalars()
        .all()
    )
    contradictions = (
        (await db.execute(select(Contradiction).where(Contradiction.run_id == run_id)))
        .scalars()
        .all()
    )
    bundle: dict[str, Any] = {
        "run": {
            "id": str(run.id),
            "tenant_id": run.tenant_id,
            "ticker": run.ticker,
            "question": run.question,
            "status": run.status,
            "thesis_json": run.thesis_json,
            "quality_passed": run.quality_passed,
            "quality_report": run.quality_report,
            "replay_of": str(run.replay_of) if run.replay_of else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
        "hops": [
            {
                "id": str(h.id),
                "agent": h.agent,
                "intent": h.intent,
                "payload": h.payload,
                "duration_ms": h.duration_ms,
            }
            for h in hops
        ],
        "matrix_rows": [
            {
                "theme": m.theme,
                "summary": m.summary,
                "confidence": m.confidence,
                "evidence": m.evidence,
                "citation_ids": m.citation_ids,
            }
            for m in matrix
        ],
        "contradictions": [
            {
                "tension_type": c.tension_type,
                "description": c.description,
                "side_a": c.side_a_citation_ids,
                "side_b": c.side_b_citation_ids,
            }
            for c in contradictions
        ],
    }
    bundle["local_learning"] = compute_local_learning_signals(bundle)
    return bundle
