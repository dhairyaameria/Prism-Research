"""Google ADK SequentialAgent pipeline: Research → Reasoning → Contradiction → Thesis."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent

logger = logging.getLogger(__name__)


def repo_root() -> Path:
    # .../packages/adk_prism/src/adk_prism/pipeline.py -> prism/
    return Path(__file__).resolve().parents[4]


def resolved_repo_root() -> Path:
    """Prefer PRISM_REPO_ROOT only when it looks real; .env.example placeholder breaks MCP otherwise."""
    derived = repo_root()
    raw = (os.environ.get("PRISM_REPO_ROOT") or "").strip()
    if not raw or "absolute/path" in raw.lower():
        return derived
    p = Path(raw).expanduser()
    return p if p.is_dir() else derived


def mcp_server_path() -> Path:
    return (
        resolved_repo_root()
        / "mcp"
        / "prism-market-intel"
        / "src"
        / "prism_mcp_intl"
        / "server.py"
    )


def _mcp_toolset():
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from mcp import StdioServerParameters

    server = mcp_server_path()
    if not server.is_file():
        raise FileNotFoundError(f"MCP server script missing: {server}")
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=[str(server)],
                env={**os.environ},
            ),
        ),
        tool_filter=[
            "get_earnings_transcript",
            "get_recent_filings",
            "get_news_digest",
        ],
    )


def build_root_agent(*, include_mcp: bool = True, llm_model: str) -> SequentialAgent:
    research_tools = []
    if include_mcp:
        try:
            research_tools.append(_mcp_toolset())
        except Exception as e:  # noqa: BLE001
            logger.warning("MCP toolset disabled: %s", e)

    research_agent = LlmAgent(
        name="ResearchAgent",
        model=llm_model,
        description="Retrieves internal context and calls MCP market-intel tools.",
        instruction="""
You are the Research agent for Prism (investment research).
You may call MCP tools: get_earnings_transcript, get_recent_filings, get_news_digest.
The user message includes an INTERNAL_CORPUS excerpt — treat it as authoritative for numbers and quotes.

After tools return, output **only** valid JSON (no markdown fences). Keep it small for local LLMs:
- **items**: at most **5** themes; each raw_notes ≤ 180 chars; ≤ 3 evidence objects per theme; chunk_excerpt ≤ 120 chars.
- **mcp_digest**: ≤ 400 chars.

Shape:
{
  "items": [
    {"theme": "string", "evidence": [{"chunk_excerpt": "string", "source_hint": "transcript|filing|news|internal"}], "raw_notes": "string"}
  ],
  "mcp_digest": "one paragraph summarizing MCP tool results"
}
        """.strip(),
        tools=research_tools,
        output_key="research_json",
    )

    reasoning_agent = LlmAgent(
        name="ReasoningAgent",
        model=llm_model,
        description="Clusters research into claims.",
        instruction="""
You are the Reasoning agent. Use the JSON in state key research_json:
{research_json}

Produce **only** JSON. At most **8** claims; each text ≤ 200 chars.
{
  "claims": [
    {"text": "string", "supports_themes": ["theme names"]}
  ]
}
        """.strip(),
        output_key="reasoning_json",
    )

    contradiction_agent = LlmAgent(
        name="ContradictionAgent",
        model=llm_model,
        description="Finds tension between narrative and disclosures.",
        instruction="""
You are the Contradiction agent. Compare optimistic narrative vs cautious risk language.
State keys available:
research_json: {research_json}
reasoning_json: {reasoning_json}

Output **only** JSON. At most **5** contradictions; description ≤ 200 chars; side_a/side_b ≤ 140 chars each.
{
  "contradictions": [
    {
      "tension_type": "narrative_vs_filing|news_vs_management|other",
      "description": "string",
      "side_a": "short quote or paraphrase",
      "side_b": "short quote or paraphrase"
    }
  ]
}
        """.strip(),
        output_key="contradiction_json",
    )

    thesis_agent = LlmAgent(
        name="ThesisAgent",
        model=llm_model,
        description="Builds matrix + thesis with citations references.",
        instruction="""
You are the Thesis agent. Combine prior JSON outputs:
research_json: {research_json}
reasoning_json: {reasoning_json}
contradiction_json: {contradiction_json}

Speed / size constraints (local models): keep output compact.
- matrix_rows: **at most 4** items (pick the highest-signal themes only).
- Each summary ≤ 220 chars; evidence ≤ 160 chars; narrative ≤ 700 chars.
- bull_points / bear_points: **at most 3** bullets each, each ≤ 120 chars.

Output **only** JSON (no markdown fences):
{
  "stance": "bull|bear|neutral|mixed",
  "narrative": "2-4 sentence executive summary",
  "matrix_rows": [
    {
      "theme": "revenue|margin|guidance|AI strategy|risk|...",
      "summary": "string",
      "confidence": 0.0-1.0,
      "evidence": "short excerpt",
      "citation_labels": ["internal#chunk", "mcp:transcript", "mcp:filing", "mcp:news"]
    }
  ],
  "bull_points": ["bullet strings"],
  "bear_points": ["bullet strings"]
}
        """.strip(),
        output_key="thesis_json",
    )

    return SequentialAgent(
        name="PrismPipeline",
        description="Research → Reasoning → Contradiction → Thesis",
        sub_agents=[research_agent, reasoning_agent, contradiction_agent, thesis_agent],
    )


def parse_agent_json_blob(text: str) -> dict:
    """Best-effort parse model output into dict."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return json.loads(t)
