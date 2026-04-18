"""Resolve LLM id for Google ADK and configure LiteLLM for OpenAI-compatible hosts."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _uses_litellm_route(model: str) -> bool:
    """True when ADK routes the model through LiteLLM (not the native Gemini API)."""
    return "/" in model and not model.startswith("gemini-")


def resolve_adk_model() -> str:
    """Return model string for LlmAgent.

    - **Gemini (default):** unset `PRISM_ADK_MODEL` or use a `gemini-*` id — uses `GOOGLE_API_KEY`.
    - **Baseten:** `PRISM_ADK_MODEL=openai/<slug>` plus `BASETEN_API_KEY` (optional `BASETEN_OPENAI_BASE`).
    - **Local OpenAI-compatible (vLLM, llama.cpp server, TGI, etc.):**
      `PRISM_ADK_MODEL=openai/<server_model_id>` plus `PRISM_OPENAI_BASE` (e.g. ``http://127.0.0.1:8000/v1``).
      Optional `PRISM_OPENAI_API_KEY` (many local servers ignore it).
    - **Ollama (open weights, local):** `PRISM_ADK_MODEL=ollama/<tag>` or `ollama_chat/<tag>`;
      optional `PRISM_OLLAMA_BASE` (default ``http://127.0.0.1:11434``). Sets `OLLAMA_API_BASE` for LiteLLM.

    Provider-style ids (`provider/model`) require `google-adk[extensions]` (LiteLLM), already pulled by `prism-api`.
    """
    model = (
        os.environ.get("PRISM_ADK_MODEL")
        or os.environ.get("PRISM_GEMINI_MODEL")
        or "gemini-2.0-flash"
    ).strip()

    if model.startswith("openai/") and os.environ.get("BASETEN_API_KEY"):
        base = os.environ.get("BASETEN_OPENAI_BASE", "https://inference.baseten.co/v1").rstrip("/")
        os.environ["OPENAI_API_KEY"] = os.environ["BASETEN_API_KEY"]
        os.environ["OPENAI_API_BASE"] = base
        logger.info("Using Baseten OpenAI-compatible endpoint at %s for model %s", base, model)
    elif model.startswith("openai/") and os.environ.get("PRISM_OPENAI_BASE", "").strip():
        base = os.environ["PRISM_OPENAI_BASE"].strip().rstrip("/")
        key = (os.environ.get("PRISM_OPENAI_API_KEY") or "not-needed").strip() or "not-needed"
        os.environ["OPENAI_API_BASE"] = base
        os.environ["OPENAI_API_KEY"] = key
        logger.info("Using local OpenAI-compatible endpoint at %s for model %s", base, model)
    elif model.startswith("ollama/") or model.startswith("ollama_chat/"):
        base = (os.environ.get("PRISM_OLLAMA_BASE") or "http://127.0.0.1:11434").strip().rstrip("/")
        os.environ["OLLAMA_API_BASE"] = base
        logger.info("Using Ollama at %s for model %s", base, model)
    elif "/" in model and not model.startswith("gemini-"):
        logger.info("Using LiteLLM-style model id (set provider env yourself): %s", model)

    if not _uses_litellm_route(model) and not os.environ.get("GOOGLE_API_KEY", "").strip():
        raise RuntimeError(
            f"GOOGLE_API_KEY is missing but the model {model!r} uses the Google Gemini API. "
            "Set GOOGLE_API_KEY in prism/.env, or use an open/local model instead, e.g. "
            "PRISM_ADK_MODEL=ollama/llama3.1 with Ollama running, or PRISM_ADK_MODEL=openai/<id> "
            "with PRISM_OPENAI_BASE pointing at your vLLM/OpenAI-compatible server."
        )

    return model
