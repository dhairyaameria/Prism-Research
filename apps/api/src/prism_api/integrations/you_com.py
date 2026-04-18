"""You.com YDC Search API — https://docs.you.com/api-reference/search/v1-search.md"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

YDC_SEARCH_URL = os.environ.get("YOU_COM_SEARCH_URL", "https://ydc-index.io/v1/search")


def you_search_sync(*, query: str, count: int = 8, freshness: str = "week") -> dict[str, Any]:
    key = os.environ.get("YOU_API_KEY", "").strip()
    if not key:
        raise RuntimeError("YOU_API_KEY is not set")

    params = {"query": query, "count": str(count), "freshness": freshness}
    with httpx.Client(timeout=45.0) as client:
        r = client.get(YDC_SEARCH_URL, params=params, headers={"X-API-Key": key})
        r.raise_for_status()
        return r.json()


def ydc_snippets_from_payload(payload: dict[str, Any], *, max_items: int = 6) -> list[dict[str, Any]]:
    """Normalize YDC /v1/search JSON into title/body/url rows (same shape as MCP get_news_digest)."""
    out: list[dict[str, Any]] = []
    results = (payload.get("results") or {}) if isinstance(payload, dict) else {}
    for row in results.get("news") or []:
        if not isinstance(row, dict) or len(out) >= max_items:
            break
        out.append(
            {
                "title": str(row.get("title") or ""),
                "body": str(row.get("description") or "")[:800],
                "url": row.get("url"),
                "kind": "news",
            }
        )
    for row in results.get("web") or []:
        if not isinstance(row, dict) or len(out) >= max_items:
            break
        snippets = row.get("snippets") or []
        desc = (snippets[0] if snippets else row.get("description") or "") or ""
        out.append(
            {
                "title": str(row.get("title") or ""),
                "body": str(desc)[:800],
                "url": row.get("url"),
                "kind": "web",
            }
        )
    return out[:max_items]
