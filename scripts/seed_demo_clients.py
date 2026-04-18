#!/usr/bin/env python3
"""Seed Postgres with demo earnings + filings for three named demo clients.

Run from repo root (same PYTHONPATH as the API):
  PYTHONPATH=apps/api/src:. python3.11 scripts/seed_demo_clients.py

Requires DATABASE_URL / .env pointing at your Prism Postgres (e.g. docker compose on 5433).
Idempotent: removes prior documents for these tenant_ids, then re-ingests.

If you already seeded under legacy tickers FRAN / ANDY / CARL, either re-run this script or apply
scripts/migrations/004_rename_demo_tickers_to_company.sql (via ./scripts/apply_migrations.sh) so rows match
FRANCLOUD / MERIDIAN / SABLE without wiping data.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select

from prism_api.db import SessionLocal
from prism_api.models import Document, TenantMember
from prism_api.services.ingest_service import ingest_documents

TENANT_IDS = ("frustrated_fran", "anxious_andy", "cautious_carl")

DEMO_PRINCIPAL = "demo@prism.local"

# Second-wave ingest (filing-only) per client: extra chunks + varied wording so retrieval / matrix confidences spread.
SUPPLEMENT_FILINGS: dict[str, str] = {
    "frustrated_fran": """
Supplemental disclosure — FranCloud Inc. (FRANCLOUD) — Analyst confidence workbook (internal)

Scenario stress: high confidence (0.86) that renewal cohort NPS recovers post-UI if ticket backlog clears within 45 days.
Low confidence (0.38) that enterprise expansion re-accelerates without a dedicated customer success pod.
Medium confidence (0.61) that gross margin normalizes once onboarding mix stabilizes.

Calibration note: confidence scores are illustrative for disclosure review; not GAAP metrics.
""".strip(),
    "anxious_andy": """
Supplemental disclosure — Meridian Logistics (MERIDIAN) — Liquidity scenario grid (internal)

High confidence (0.81) that revolver covenant headroom covers 9 months at current burn if spot rates stay flat.
Low confidence (0.34) that legal reserve is sufficient if inquiry widens beyond voluntary document production.
Medium confidence (0.57) that working capital release funds one quarter of opex if freight volumes rebound modestly.

Calibration note: confidence bands widen under macro stress; treat as directional only.
""".strip(),
    "cautious_carl": """
Supplemental disclosure — Sable Instruments (SABLE) — Revenue timing sensitivity (internal)

High confidence (0.88) that acceptance-test deferrals explain the Q4 guide cut without implying demand collapse.
Low confidence (0.29) that legacy SKU reserves are fully adequate if fab pushouts extend past one quarter.
Medium confidence (0.64) that book-to-bill above one still converts if acceptance cadence returns to historical norms.

Calibration note: model uses conservative acceptance curves; confidence not comparable quarter-to-quarter.
""".strip(),
}


CLIENTS: list[dict[str, str]] = [
    {
        "tenant_id": "frustrated_fran",
        "ticker": "FRANCLOUD",
        "display_name": 'Frustrated Frances',
        "transcript": """
Q3 FY2026 earnings call — FranCloud Inc. (ticker FRANCLOUD)

Operator: Welcome. FranCloud provides workflow automation for mid-market finance teams.

CEO: Another strong quarter. Revenue up 22% year over year. We are winning in the enterprise and our pipeline has never been healthier.

CFO: We delivered adjusted EBITDA ahead of the high end of our guide. Free cash flow improved sequentially as we disciplined opex while still investing in the platform.

Analyst (River Capital): Thanks. NPS scores slipped in the appendix — can you square that with the "best product satisfaction" comment on the last call?

CEO: We had a noisy quarter from a UI refresh. Long-term satisfaction is intact; we already shipped fixes and early reads are positive.

Analyst (Harbor Point): Support ticket volumes are up 40% YoY in the KPI deck. What gives?

CEO: Volume reflects adoption, not quality issues. We are scaling support ahead of demand.

CFO: We reclassified a portion of implementation revenue to professional services; no change to cash economics.

Analyst (River Capital): Gross margin expanded less than modeled. Is pricing power intact?

CEO: Absolutely. Mix shift and one-time onboarding costs. Next year we expect margin expansion to resume.

Closing: Management reiterated confidence in the long-term model and declined to take a follow-up on churn.
""".strip(),
        "filing_excerpt": """
Item 1A — Risk Factors (excerpt), FranCloud Inc. Form 10-Q

Customer dissatisfaction: If we fail to resolve product quality or usability issues in a timely manner, customers may reduce usage, delay renewals, or churn to competitors. During the quarter we experienced elevated support tickets following a user interface redesign.

Churn: Our net revenue retention may decline if expansion within existing accounts slows or if downgrades increase. Certain cohorts showed higher downgrade rates tied to the UI refresh.

Management credibility: Statements regarding customer satisfaction and roadmap delivery are subject to risks and uncertainties. Actual outcomes may differ materially from projections.

Competition: Competitors may introduce superior features or pricing, which could erode our win rates and pressure margins despite management commentary on pricing power.
""".strip(),
        "internal_notes": """
Analyst desk — Frances  (client). Tone on calls: visibly irritated with generic answers; pushes on tickets/NPS/churn.
Wants contradictions between "everything is fine" narrative and ops metrics. Prefer direct citations from transcript vs. 10-Q risk language.
""".strip(),
    },
    {
        "tenant_id": "anxious_andy",
        "ticker": "MERIDIAN",
        "display_name": 'Anxious Andrew',
        "transcript": """
Q3 FY2026 — Meridian Logistics (ticker MERIDIAN) earnings call

CEO: Thank you for joining. Meridian operates a digital freight marketplace across North America.

CFO: Revenue grew 8% YoY on a constant-currency basis, below our initial expectations for the year. Adjusted EBITDA was roughly flat as we absorbed higher insurance and fuel volatility.

CEO: The macro backdrop remains uncertain. We are seeing elongated sales cycles in enterprise accounts and some softness in spot volumes in select lanes.

Analyst: Can you quantify downside if industrial production weakens further?

CFO: We are not providing a new baseline scenario today. We are evaluating a range of outcomes and will update guidance when visibility improves.

CEO: We have stress-tested liquidity and believe we have adequate flexibility, but we are monitoring working capital closely.

Analyst: Any comment on the DOJ inquiry mentioned in press reports?

CEO: We received a voluntary information request. We are cooperating fully. We cannot predict timing or outcome.

CFO: We recorded a small legal reserve; the range of loss is uncertain.

Closing: Management emphasized caution and declined to reaffirm multi-year targets.
""".strip(),
        "filing_excerpt": """
Item 1A — Risk Factors (excerpt), Meridian Logistics Form 10-Q

Macroeconomic conditions: Our business is sensitive to industrial production, consumer spending, and interest rates. A prolonged downturn could reduce shipment volumes and compress take rates.

Legal and regulatory: We are subject to inquiries and investigations that could result in fines, penalties, or operational restrictions. The outcome and timing of such matters are inherently uncertain.

Liquidity: If market conditions deteriorate, we may face higher cost of capital or reduced access to credit, which could affect our ability to fund operations and growth initiatives.

Going concern: While management believes our plans alleviate substantial doubt, those plans depend on achieving forecasted cost reductions and revenue stabilization, which may not occur.
""".strip(),
        "internal_notes": """
Coverage — Andrew (client). Worries about tail risks and legal overhang; wants every hedge word mapped to filings.
Flag any mismatch between "adequate flexibility" language and going-concern-style risks.
""".strip(),
    },
    {
        "tenant_id": "cautious_carl",
        "ticker": "SABLE",
        "display_name": "Cautious Carl",
        "transcript": """
Q3 FY2026 — Sable Instruments (ticker SABLE) earnings call

CEO: Sable designs precision measurement tools for semiconductor and advanced manufacturing customers.

CFO: We beat revenue consensus by 2% and delivered EPS in line with expectations. However, we are lowering Q4 revenue guidance by approximately 6% at the midpoint due to pushouts in tool deliveries tied to fab timing.

CEO: Our backlog remains healthy and book-to-bill was above one. We are choosing not to chase low-margin opportunistic revenue.

CFO: Gross margin held steady; we increased inventory reserves modestly for a specific legacy product line approaching end of life.

Analyst: Why guide down if backlog is strong?

CEO: We recognize revenue on shipment and customer acceptance. A handful of large tools slipped out of the fiscal quarter; we prefer conservative recognition.

CFO: We maintained full-year EPS by tightening opex and pausing non-critical hires.

Analyst: Any change to capital return policy?

CFO: No share repurchases this quarter; we are preserving cash flexibility given the delivery slippage.

Closing: Management reiterated long-term targets but emphasized near-term prudence.
""".strip(),
        "filing_excerpt": """
Item 7 — MD&A excerpt, Sable Instruments Form 10-Q

Revenue recognition: We recognize revenue for certain tools upon customer acceptance testing. Delays in acceptance or changes in customer schedules may shift revenue between periods. We apply conservative assumptions when estimating progress toward acceptance.

Inventory and obsolescence: We maintain reserves for excess and obsolete inventory, particularly for products nearing end of life. Changes in demand could require additional reserves.

Guidance: Forward-looking statements are based on assumptions that may prove incorrect. Actual results may differ materially from guidance due to supply chain, customer concentration, and timing of shipments.

Risk factors: Customer concentration in advanced nodes may increase volatility. A small number of customers represent a significant portion of revenue.
""".strip(),
        "internal_notes": """
Institutional — Carl (client). Skeptical of beat-and-lower patterns; wants alignment between conservative MD&A and headline "healthy backlog" statements.
""".strip(),
    },
]


async def _clear_demo_documents() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(TenantMember).where(TenantMember.tenant_id.in_(TENANT_IDS)))
        await session.execute(delete(Document).where(Document.tenant_id.in_(TENANT_IDS)))
        await session.commit()


async def _ensure_demo_members() -> None:
    """So PRISM_RBAC_STRICT=1 demos work with X-Prism-Principal: demo@prism.local."""
    async with SessionLocal() as session:
        for tid in TENANT_IDS:
            res = await session.execute(
                select(TenantMember).where(TenantMember.tenant_id == tid, TenantMember.principal == DEMO_PRINCIPAL)
            )
            if res.scalar_one_or_none() is None:
                session.add(TenantMember(tenant_id=tid, principal=DEMO_PRINCIPAL, role="analyst"))
        await session.commit()


async def main() -> None:
    print("Clearing demo tenant documents + demo tenant members…")
    await _clear_demo_documents()
    await _ensure_demo_members()

    for c in CLIENTS:
        tid = c["tenant_id"]
        tick = c["ticker"]
        print(f"Ingesting {c['display_name']} → tenant={tid} ticker={tick}…")
        async with SessionLocal() as session:
            ids = await ingest_documents(
                session,
                tenant_id=tid,
                ticker=tick,
                transcript=c["transcript"],
                filing_excerpt=c["filing_excerpt"],
                internal_notes=c["internal_notes"],
            )
            sup = SUPPLEMENT_FILINGS.get(tid)
            if sup:
                ids2 = await ingest_documents(
                    session,
                    tenant_id=tid,
                    ticker=tick,
                    transcript=None,
                    filing_excerpt=sup,
                    internal_notes=None,
                )
                ids = {**ids, **{f"supplement_{k}": v for k, v in ids2.items()}}
        print(f"  done: {ids}")

    print()
    print("Summary (use these in the UI / API):")
    for c in CLIENTS:
        print(f"  • {c['display_name']}: X-Prism-Tenant={c['tenant_id']!r}  ticker={c['ticker']!r}")
    print(f"Optional RBAC principal: {DEMO_PRINCIPAL!r} (analyst on all three tenants)")


if __name__ == "__main__":
    asyncio.run(main())
