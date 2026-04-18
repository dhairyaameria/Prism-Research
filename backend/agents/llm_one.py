"""Single-turn LLM call: Ollama native HTTP, else LiteLLM `acompletion` (OpenAI-compatible → Baseten/vLLM/etc.)."""

from __future__ import annotations

import os

from backend.agents.ollama_client import chat_completion as ollama_chat


def _litellm_model_id(model_id: str) -> str:
    """LiteLLM treats the first `openai/` as its provider tag and sends the rest as the HTTP `model` field.

    Baseten catalog ids can be `openai/gpt-oss-120b` (see /v1/models). Passing `openai/gpt-oss-120b` would make
    LiteLLM send `gpt-oss-120b` → 404. Prefix once so the outbound model becomes `openai/gpt-oss-120b`.
    """
    mid = (model_id or "").strip()
    if not mid.startswith("openai/"):
        return mid
    base = (os.environ.get("OPENAI_API_BASE") or "").lower()
    if "baseten.co" not in base:
        return mid
    if mid.startswith("openai/openai/"):
        return mid
    rest = mid[len("openai/"):]
    if "/" not in rest:
        return f"openai/openai/{rest}"
    return mid


async def complete_one(model_id: str, *, system: str, user: str, json_mode: bool = False) -> str:
    mid = _litellm_model_id((model_id or "").strip())
    if mid.startswith("ollama/") or mid.startswith("ollama_chat/"):
        return await ollama_chat(mid, system=system, user=user, format_json=json_mode)
    from litellm import acompletion

    resp = await acompletion(
        model=mid,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    choice = resp.choices[0]
    msg = getattr(choice, "message", None) or choice.get("message", {})
    content = getattr(msg, "content", None) if msg is not None else None
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"unexpected LLM response shape: {resp!r:.600}")
    return content
