"""MCP server: market intel tools for Prism Research agent (mock + You.com live search)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("prism-market-intel")

YDC_SEARCH = os.environ.get("YOU_COM_SEARCH_URL", "https://ydc-index.io/v1/search")


def _mock_news_digest(ticker: str, days_back: int) -> dict:
    t = ticker.upper()
    now = datetime.now(UTC)
    return {
        "ticker": t,
        "days_back": days_back,
        "articles": [
            {
                "title": f"{t} beats revenue expectations",
                "outlet": "MockWire",
                "published_at": (now - timedelta(days=2)).isoformat(),
                "summary": "Analysts cite strong bookings momentum.",
            },
            {
                "title": f"Investors question {t} margin durability",
                "outlet": "DemoTimes",
                "published_at": (now - timedelta(days=1)).isoformat(),
                "summary": "Article notes CFO hedging language on sustainability of margin gains.",
            },
        ],
        "fetched_at": now.isoformat(),
        "source": "mock",
    }


def _you_news_digest(ticker: str, days_back: int) -> dict:
    """You.com YDC unified search — LLM-ready web + news JSON."""
    key = os.environ["YOU_API_KEY"].strip()
    t = ticker.upper()
    q = f"{t} stock earnings guidance analyst headlines SEC filing risks last {days_back} days"
    with httpx.Client(timeout=45.0) as client:
        r = client.get(
            YDC_SEARCH,
            params={"query": q, "count": 10, "freshness": "week", "language": "EN"},
            headers={"X-API-Key": key},
        )
        r.raise_for_status()
        payload = r.json()

    articles: list[dict] = []
    results = (payload.get("results") or {}) if isinstance(payload, dict) else {}
    for row in results.get("news") or []:
        if isinstance(row, dict):
            articles.append(
                {
                    "title": row.get("title", ""),
                    "outlet": "news",
                    "published_at": row.get("page_age") or "",
                    "summary": (row.get("description") or "")[:500],
                    "url": row.get("url"),
                }
            )
    for row in (results.get("web") or [])[:6]:
        if isinstance(row, dict):
            snippets = row.get("snippets") or []
            articles.append(
                {
                    "title": row.get("title", ""),
                    "outlet": "web",
                    "published_at": row.get("page_age") or "",
                    "summary": (snippets[0] if snippets else row.get("description") or "")[:500],
                    "url": row.get("url"),
                }
            )

    meta = payload.get("metadata") or {}
    return {
        "ticker": t,
        "days_back": days_back,
        "articles": articles,
        "fetched_at": datetime.now(UTC).isoformat(),
        "source": "you.com",
        "search_uuid": meta.get("search_uuid"),
        "latency": meta.get("latency"),
    }


@mcp.tool()
def get_earnings_transcript(ticker: str) -> str:
    """Return a short mock earnings call excerpt for the given ticker."""
    t = ticker.upper()
    body = (
        f"Q4 prepared remarks for {t}: management highlighted resilient demand, "
        f"noted gross margin expanded 120bps YoY, and guided next quarter revenue "
        f"flat to slightly up. CFO cautioned FX headwinds could reduce reported growth by ~1%."
    )
    return json.dumps(
        {
            "ticker": t,
            "quarter": "Q4",
            "excerpt": body,
            "tone": "constructive_with_caution",
            "fetched_at": datetime.now(UTC).isoformat(),
        }
    )


@mcp.tool()
def get_recent_filings(ticker: str) -> str:
    """Return mock 10-Q / risk factor language for contradiction checks."""
    t = ticker.upper()
    risks = (
        f"Item 1A in latest 10-Q for {t} states competitive pressures may constrain pricing power; "
        f"macro uncertainty could delay enterprise purchasing decisions. "
        f"Management previously indicated gross margin expansion may not be sustainable beyond two quarters."
    )
    return json.dumps(
        {
            "ticker": t,
            "filing_type": "10-Q",
            "risk_excerpt": risks,
            "fetched_at": datetime.now(UTC).isoformat(),
        }
    )


@mcp.tool()
def get_news_digest(ticker: str, days_back: int = 7) -> str:
    """Recent headlines: uses You.com Search API when YOU_API_KEY is set, else high-fidelity mock."""
    if os.environ.get("YOU_API_KEY", "").strip():
        try:
            return json.dumps(_you_news_digest(ticker, days_back))
        except Exception:
            fallback = _mock_news_digest(ticker, days_back)
            fallback["source"] = "mock_after_you_error"
            return json.dumps(fallback)
    return json.dumps(_mock_news_digest(ticker, days_back))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
