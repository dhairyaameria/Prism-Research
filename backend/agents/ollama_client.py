"""Ollama HTTP client: embeddings (optional) and chat completions for the fast pipeline."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


def ollama_base() -> str:
    return (os.environ.get("PRISM_OLLAMA_BASE") or "http://127.0.0.1:11434").rstrip("/")


def strip_ollama_model_tag(model_id: str) -> str:
    m = (model_id or "").strip()
    if m.startswith("ollama_chat/"):
        return m[len("ollama_chat/") :]
    if m.startswith("ollama/"):
        return m[len("ollama/") :]
    return m


async def embed_query(prompt: str, *, embed_model: str | None = None) -> list[float]:
    """POST /api/embeddings. If no model configured, caller should use prism_api embed_texts instead."""
    model = (embed_model or os.environ.get("PRISM_OLLAMA_EMBED_MODEL") or "").strip()
    if not model:
        raise RuntimeError("PRISM_OLLAMA_EMBED_MODEL not set; use prism_api.services.embeddings.embed_texts for query")
    url = f"{ollama_base()}/api/embeddings"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json={"model": model, "prompt": prompt})
        r.raise_for_status()
        data = r.json()
        emb = data.get("embedding")
        if not isinstance(emb, list):
            raise RuntimeError(f"unexpected embeddings response: {data!r:.500}")
        return [float(x) for x in emb]


async def chat_completion(
    model_id: str,
    *,
    system: str,
    user: str,
    timeout_s: float = 300.0,
    format_json: bool = False,
) -> str:
    """Non-streaming chat; model_id may be `ollama/llama3.1` style."""
    tag = strip_ollama_model_tag(model_id)
    url = f"{ollama_base()}/api/chat"
    payload: dict[str, Any] = {
        "model": tag,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if format_json:
        payload["format"] = "json"
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"unexpected chat response: {json.dumps(data)[:800]}")
    if not content.strip():
        raise RuntimeError("Ollama returned empty message content (try json format or a larger context model)")
    return content
