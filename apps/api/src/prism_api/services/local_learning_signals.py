"""Client-side local learning layer (demo): signals when evidence may sit behind another tenant boundary."""

from __future__ import annotations

from typing import Any


def _research_payload(hops: list[dict[str, Any]]) -> dict[str, Any] | None:
    for h in hops:
        if h.get("agent") != "Research":
            continue
        p = h.get("payload")
        if isinstance(p, dict) and "vector_chunk_count" in p:
            return p
    return None


def _analysis_payload(hops: list[dict[str, Any]]) -> dict[str, Any] | None:
    for h in hops:
        if h.get("agent") != "Analysis":
            continue
        p = h.get("payload")
        if isinstance(p, dict):
            return p
    return None


def compute_local_learning_signals(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Lightweight federated-style boundary hint: uses retrieval thickness + quality gate + matrix
    confidence (no extra LLM). Analyst feedback / LoRA updates would consume these signals upstream
    in a full deployment; here we surface them for optional evidence-access UX.
    """
    run = bundle.get("run") or {}
    hops = bundle.get("hops") or []
    if not isinstance(hops, list):
        hops = []
    matrix = bundle.get("matrix_rows") or []
    if not isinstance(matrix, list):
        matrix = []

    qreport = run.get("quality_report") if isinstance(run.get("quality_report"), dict) else {}
    warnings = qreport.get("warnings") if isinstance(qreport.get("warnings"), list) else []
    reasons = qreport.get("reasons") if isinstance(qreport.get("reasons"), list) else []

    research = _research_payload(hops)
    analysis = _analysis_payload(hops)
    vec_n: int | None = None
    you_n: int | None = None
    top_scores: list[float] = []
    if research is not None:
        try:
            vec_n = int(research.get("vector_chunk_count") or 0)
        except (TypeError, ValueError):
            vec_n = 0
        try:
            you_n = int(research.get("you_com_chunk_count") or 0)
        except (TypeError, ValueError):
            you_n = 0
        raw_ts = research.get("top_scores")
        if isinstance(raw_ts, list):
            for x in raw_ts[:5]:
                if isinstance(x, (int, float)):
                    top_scores.append(float(x))

    claim_n = 0
    if analysis is not None:
        try:
            claim_n = int(analysis.get("claims_n") or analysis.get("claim_count") or 0)
        except (TypeError, ValueError):
            claim_n = 0

    signals: list[str] = []
    score = 0.0

    if vec_n is not None:
        if vec_n == 0:
            signals.append("no_internal_chunks")
            score += 0.55
        elif vec_n <= 2:
            signals.append("thin_internal_retrieval")
            score += 0.38
        elif vec_n <= 4:
            signals.append("weak_internal_retrieval")
            score += 0.18

    if top_scores:
        best = max(top_scores)
        if best < 0.38:
            signals.append("weak_vector_scores")
            score += 0.22
        elif best < 0.48:
            signals.append("muted_vector_scores")
            score += 0.1

    if vec_n is not None and vec_n >= 5 and claim_n <= 1:
        signals.append("many_chunks_few_claims")
        score += 0.28

    if run.get("quality_passed") is False:
        signals.append("quality_gate_failed")
        score += 0.22
    if "no_claims_from_analysis" in warnings:
        signals.append("no_structured_claims")
        score += 0.2
    if "empty_matrix_rows" in reasons:
        signals.append("empty_evidence_matrix")
        score += 0.15

    confs: list[float] = []
    for m in matrix:
        if not isinstance(m, dict):
            continue
        c = m.get("confidence")
        if isinstance(c, (int, float)):
            confs.append(float(c))
    if confs:
        avg_c = sum(confs) / len(confs)
        if avg_c < 0.4:
            signals.append("low_matrix_confidence")
            score += 0.18
        elif avg_c < 0.55:
            signals.append("muted_matrix_confidence")
            score += 0.08

    # Fast pipeline: Research hop carries counts/scores. ADK omits them; quality/matrix still contribute.
    suggest = score >= 0.42 or (vec_n is not None and vec_n <= 1 and score >= 0.25)

    narrative_parts: list[str] = []
    if vec_n is not None:
        narrative_parts.append(f"internal retrieval: {vec_n} chunk(s)")
    if you_n is not None and you_n > 0:
        narrative_parts.append(f"You.com context: {you_n} snippet(s)")
    if run.get("quality_passed") is False:
        narrative_parts.append("quality gate did not pass")

    return {
        "suggest_team_boundary_request": bool(suggest),
        "confidence": round(min(1.0, score), 3),
        "signals": signals,
        "retrieval_summary": {
            "vector_chunks": vec_n,
            "you_com_chunks": you_n,
        },
        "narrative": "; ".join(narrative_parts) if narrative_parts else "boundary hint from quality and matrix only",
    }
