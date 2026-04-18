"""Optional Veris AI Python SDK — exposes FastAPI routes as MCP for Veris packaging."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def mount_veris_fastapi_mcp(app: FastAPI) -> bool:
    """When ENABLE_VERIS_MCP=1, mount Veris-compatible MCP on this FastAPI app."""
    if os.environ.get("ENABLE_VERIS_MCP", "").lower() not in ("1", "true", "yes"):
        return False
    try:
        from veris_ai import veris
    except ImportError:
        logger.warning("ENABLE_VERIS_MCP is set but veris-ai is not installed. pip install 'veris-ai[fastapi]'")
        return False

    veris.set_fastapi_mcp(
        fastapi=app,
        name="Prism",
        description="Prism investment-research agent (ingest, runs, eval) for Veris simulation",
    )
    veris.fastapi_mcp.mount_http()
    logger.info("Veris FastAPI MCP mounted (see Veris docs for `veris env push`).")
    return True
