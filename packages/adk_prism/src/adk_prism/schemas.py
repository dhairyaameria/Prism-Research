"""Structured JSON shapes persisted from agent outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResearchEvidence(BaseModel):
    chunk_excerpt: str = ""
    source_hint: str = ""


class ResearchItem(BaseModel):
    theme: str
    evidence: list[ResearchEvidence] = Field(default_factory=list)
    raw_notes: str = ""


class ResearchPayload(BaseModel):
    items: list[ResearchItem] = Field(default_factory=list)
    mcp_digest: str = ""


class ReasoningClaim(BaseModel):
    text: str
    supports_themes: list[str] = Field(default_factory=list)


class ReasoningPayload(BaseModel):
    claims: list[ReasoningClaim] = Field(default_factory=list)


class ContradictionItem(BaseModel):
    tension_type: str = "narrative_vs_filing"
    description: str
    side_a: str = ""
    side_b: str = ""


class ContradictionPayload(BaseModel):
    contradictions: list[ContradictionItem] = Field(default_factory=list)


class MatrixRowOut(BaseModel):
    theme: str
    summary: str
    confidence: float = 0.75
    evidence: str = ""
    citation_labels: list[str] = Field(default_factory=list)


class ThesisPayload(BaseModel):
    stance: str = "mixed"
    narrative: str = ""
    matrix_rows: list[MatrixRowOut] = Field(default_factory=list)
    bull_points: list[str] = Field(default_factory=list)
    bear_points: list[str] = Field(default_factory=list)


def safe_parse(model: type[BaseModel], data: Any) -> BaseModel:
    if isinstance(data, BaseModel):
        return data
    if isinstance(data, dict):
        return model.model_validate(data)
    if isinstance(data, str):
        return model.model_validate_json(data)
    return model.model_validate({})
