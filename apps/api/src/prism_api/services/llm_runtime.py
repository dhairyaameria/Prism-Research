"""Per-tenant LLM routing: resolve open-source / Baseten / Gemini config without storing secrets in Postgres."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from prism_api.models import TenantLlmProfile

logger = logging.getLogger(__name__)

_ENV_KEYS = ("GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENAI_API_BASE", "OLLAMA_API_BASE")

_BASETEN_PROVIDER = "baseten"


def _llm_provider() -> str:
    return (os.environ.get("PRISM_LLM_PROVIDER") or "").strip().lower()


def _require_baseten_config(*, model: str, context: str) -> None:
    if _llm_provider() != _BASETEN_PROVIDER:
        return
    if not model.startswith("openai/"):
        raise RuntimeError(
            f"{context}: PRISM_LLM_PROVIDER=baseten requires PRISM_ADK_MODEL=openai/<slug> "
            f"(Baseten Model APIs / your deployment id). Got {model!r}."
        )
    if not (os.environ.get("BASETEN_API_KEY") or "").strip():
        raise RuntimeError(f"{context}: PRISM_LLM_PROVIDER=baseten requires BASETEN_API_KEY.")


def _uses_litellm_route(model: str) -> bool:
    return "/" in model and not model.startswith("gemini-")


@dataclass(frozen=True)
class LlmRuntime:
    """Resolved credentials for one ADK invocation (never log key values)."""

    model_id: str
    google_api_key: str | None
    openai_api_key: str | None
    openai_api_base: str | None
    ollama_api_base: str | None

    @staticmethod
    def from_process_env() -> LlmRuntime:
        """Fallback when no tenant_llm_profiles row exists."""
        if _llm_provider() == _BASETEN_PROVIDER:
            model = (os.environ.get("PRISM_ADK_MODEL") or "").strip()
            if not model:
                model = (os.environ.get("PRISM_GEMINI_MODEL") or "").strip()
            if not model:
                raise RuntimeError(
                    "PRISM_LLM_PROVIDER=baseten requires PRISM_ADK_MODEL=openai/<baseten_model_slug> "
                    "(see https://docs.baseten.co/inference/model-apis/overview ; list slugs: "
                    "curl -s https://inference.baseten.co/v1/models -H \"Authorization: Api-Key $BASETEN_API_KEY\")."
                )
            _require_baseten_config(model=model, context="process env")
            obase = os.environ.get("BASETEN_OPENAI_BASE", "https://inference.baseten.co/v1").rstrip("/")
            okey = os.environ["BASETEN_API_KEY"].strip()
            return LlmRuntime(
                model_id=model,
                google_api_key=None,
                openai_api_key=okey,
                openai_api_base=obase,
                ollama_api_base=None,
            )

        model = (
            os.environ.get("PRISM_ADK_MODEL") or os.environ.get("PRISM_GEMINI_MODEL") or "gemini-2.0-flash"
        ).strip()
        gkey = (os.environ.get("GOOGLE_API_KEY") or "").strip() or None
        okey: str | None = None
        obase: str | None = None
        olbase: str | None = None

        if model.startswith("openai/") and os.environ.get("BASETEN_API_KEY"):
            obase = os.environ.get("BASETEN_OPENAI_BASE", "https://inference.baseten.co/v1").rstrip("/")
            okey = os.environ["BASETEN_API_KEY"].strip()
        elif model.startswith("openai/") and os.environ.get("PRISM_OPENAI_BASE", "").strip():
            obase = os.environ["PRISM_OPENAI_BASE"].strip().rstrip("/")
            okey = (os.environ.get("PRISM_OPENAI_API_KEY") or "not-needed").strip() or "not-needed"
        elif model.startswith("ollama/") or model.startswith("ollama_chat/"):
            olbase = (os.environ.get("PRISM_OLLAMA_BASE") or "http://127.0.0.1:11434").strip().rstrip("/")

        return LlmRuntime(
            model_id=model,
            google_api_key=gkey,
            openai_api_key=okey,
            openai_api_base=obase,
            ollama_api_base=olbase,
        )

    @staticmethod
    def from_profile_row(row: TenantLlmProfile) -> LlmRuntime:
        model = row.model_id.strip()
        if _llm_provider() == _BASETEN_PROVIDER:
            _require_baseten_config(model=model, context=f"tenant {row.tenant_id!r} llm profile")
        gname = (row.google_api_key_env or "").strip() or "GOOGLE_API_KEY"
        google_api_key = (os.environ.get(gname) or "").strip() or None

        okey: str | None = None
        obase: str | None = (row.openai_api_base or "").strip() or None
        olbase: str | None = (row.ollama_api_base or "").strip() or None

        if model.startswith("openai/"):
            key_env = (row.api_key_env or "").strip()
            if key_env:
                okey = (os.environ.get(key_env) or "").strip() or None
            if okey is None:
                okey = (os.environ.get("BASETEN_API_KEY") or "").strip() or None
            if okey is None:
                okey = (os.environ.get("PRISM_OPENAI_API_KEY") or "not-needed").strip() or None
            if not obase:
                if os.environ.get("BASETEN_API_KEY"):
                    obase = os.environ.get("BASETEN_OPENAI_BASE", "https://inference.baseten.co/v1").rstrip("/")
                else:
                    obase = (os.environ.get("PRISM_OPENAI_BASE") or "").strip().rstrip("/") or None
        elif model.startswith("ollama/") or model.startswith("ollama_chat/"):
            if not olbase:
                olbase = (os.environ.get("PRISM_OLLAMA_BASE") or "http://127.0.0.1:11434").strip().rstrip("/")

        rt = LlmRuntime(
            model_id=model,
            google_api_key=google_api_key,
            openai_api_key=okey,
            openai_api_base=obase,
            ollama_api_base=olbase,
        )
        if _llm_provider() == _BASETEN_PROVIDER:
            k = (os.environ.get("BASETEN_API_KEY") or "").strip()
            if not k:
                raise RuntimeError(
                    f"Tenant {row.tenant_id!r}: PRISM_LLM_PROVIDER=baseten requires BASETEN_API_KEY in the environment."
                )
            bbase = os.environ.get("BASETEN_OPENAI_BASE", "https://inference.baseten.co/v1").rstrip("/")
            return LlmRuntime(
                model_id=model,
                google_api_key=None,
                openai_api_key=k,
                openai_api_base=bbase,
                ollama_api_base=None,
            )
        return rt


def validate_llm_runtime(rt: LlmRuntime) -> None:
    if not _uses_litellm_route(rt.model_id) and not (rt.google_api_key or "").strip():
        raise RuntimeError(
            f"Tenant LLM uses Gemini ({rt.model_id!r}) but no Google API key resolved "
            "(set google_api_key_env to an env var that holds GOOGLE_API_KEY, or configure "
            "an open model such as ollama/... or openai/... with api_key_env / bases)."
        )
    if rt.model_id.startswith("openai/"):
        if not (rt.openai_api_base or "").strip():
            raise RuntimeError(
                "openai/ model requires openai_api_base on the tenant profile (Baseten deployment URL "
                "or vLLM base ending in /v1)."
            )
        if not (rt.openai_api_key or "").strip():
            raise RuntimeError(
                "openai/ model requires api_key_env pointing to a populated env var (e.g. "
                "BASETEN_API_KEY_ACME), or set BASETEN_API_KEY / PRISM_OPENAI_API_KEY globally."
            )


async def load_llm_runtime(session: AsyncSession, tenant_id: str) -> LlmRuntime:
    try:
        res = await session.execute(select(TenantLlmProfile).where(TenantLlmProfile.tenant_id == tenant_id))
        row = res.scalar_one_or_none()
    except ProgrammingError as e:
        # DB not migrated yet (e.g. missing tenant_llm_profiles) — keep UI alive with process env.
        logger.warning("tenant_llm_profiles query failed; using process env: %s", e)
        await session.rollback()
        return LlmRuntime.from_process_env()
    if row is None:
        return LlmRuntime.from_process_env()
    return LlmRuntime.from_profile_row(row)


@contextmanager
def use_llm_runtime(rt: LlmRuntime) -> Iterator[None]:
    """Temporarily set process env for LiteLLM / Gemini SDK (must be used under a global lock)."""
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    try:
        if rt.google_api_key:
            os.environ["GOOGLE_API_KEY"] = rt.google_api_key
        else:
            os.environ.pop("GOOGLE_API_KEY", None)

        if rt.openai_api_key:
            os.environ["OPENAI_API_KEY"] = rt.openai_api_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)

        if rt.openai_api_base:
            os.environ["OPENAI_API_BASE"] = rt.openai_api_base
        else:
            os.environ.pop("OPENAI_API_BASE", None)

        if rt.ollama_api_base:
            os.environ["OLLAMA_API_BASE"] = rt.ollama_api_base
        else:
            os.environ.pop("OLLAMA_API_BASE", None)

        validate_llm_runtime(rt)
        yield
    finally:
        for k in _ENV_KEYS:
            v = saved.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
