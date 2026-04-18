"use client";

import Link from "next/link";
import { useState } from "react";

import SystemDesignDiagram from "./SystemDesignDiagram";

const DEMO_PRINCIPAL = "demo@prism.local";

const personas = [
  {
    slug: "frustrated_fran",
    name: "Frustrated Frances",
    ticker: "FRANCLOUD",
    company: "FranCloud Inc.",
    tagline: "FranCloud — upbeat management vs. tickets, NPS, and churn in the filing",
    accent: "from-rose-950/80 to-slate-900/90 border-rose-800/50",
    question:
      "What in the 10-Q contradicts management's tone on customer satisfaction and product quality on the call?",
  },
  {
    slug: "anxious_andy",
    name: "Anxious Andrew",
    ticker: "MERIDIAN",
    company: "Meridian Logistics",
    tagline: "Meridian Logistics — macro/legal uncertainty and liquidity hedging",
    accent: "from-amber-950/80 to-slate-900/90 border-amber-800/50",
    question:
      "How do liquidity and flexibility statements on the call compare to the risk-factor language on financing and going concern?",
  },
  {
    slug: "cautious_carl",
    name: "Cautious Carl",
    ticker: "SABLE",
    company: "Sable Instruments",
    tagline: "Sable Instruments — beat with lowered guide vs. conservative MD&A",
    accent: "from-teal-950/80 to-slate-900/90 border-teal-800/50",
    question:
      "Does the backlog and demand narrative align with revenue recognition and timing disclosures in the filing?",
  },
] as const;

const NAV_TABS = [
  { id: "features", label: "Prism Features" },
  { id: "system_design", label: "Architecture Design" },
  { id: "client_simulation", label: "Client Simulation" },
  { id: "server_analysis", label: "Server Analysis" },
  { id: "use_cases", label: "Applicability" },
] as const;

type NavTabId = (typeof NAV_TABS)[number]["id"];

function workspaceHref(p: (typeof personas)[number]) {
  const q = new URLSearchParams({
    tenant: p.slug,
    ticker: p.ticker,
    principal: DEMO_PRINCIPAL,
    question: p.question,
    demo: "1",
  });
  return `/workspace?${q.toString()}`;
}

function ApplicabilityPanel() {
  return (
    <div className="mx-auto max-w-5xl space-y-10">
      <header className="text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-400/90">Applicability</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
          Who uses Prism — and where else it fits
        </h1>
        <p className="mx-auto mt-4 max-w-3xl text-sm leading-relaxed text-slate-400">
          Prism targets <strong className="text-slate-300">knowledge workers</strong> who need multi-step agent
          workflows over sensitive documents: cited answers, contradiction checks, and audit trails — with{" "}
          <strong className="text-slate-300">hard tenant isolation</strong> so corpora and runs never mix by accident.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-800 bg-prism-panel/50 p-6 sm:p-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300/95">Primary user personas</h2>
        <ul className="mt-4 grid gap-3 text-sm leading-relaxed text-slate-400 sm:grid-cols-2">
          <li className="rounded-xl border border-slate-800/80 bg-black/20 px-4 py-3">
            <strong className="text-slate-200">Equity & credit research</strong> — earnings, filings, and management
            commentary triaged into a defensible thesis with chunk-level citations.
          </li>
          <li className="rounded-xl border border-slate-800/80 bg-black/20 px-4 py-3">
            <strong className="text-slate-200">Investor relations & strategy</strong> — consistent narratives vs.
            disclosure language; internal prep without leaking peer-sensitive drafts across teams.
          </li>
          <li className="rounded-xl border border-slate-800/80 bg-black/20 px-4 py-3">
            <strong className="text-slate-200">Compliance & risk</strong> — traceable hops when comparing policies,
            controls, and incident write-ups to regulator-facing text.
          </li>
          <li className="rounded-xl border border-slate-800/80 bg-black/20 px-4 py-3">
            <strong className="text-slate-200">Multi-tenant platforms & banks</strong> — each client workspace is a
            separate <code className="text-slate-500">tenant</code> + corpus; retrieval and runs stay scoped for demos
            and production-shaped RBAC.
          </li>
        </ul>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-prism-panel/50 p-6 sm:p-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300/95">Adjacent products (same neighborhood)</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-500">
          Several well-funded teams pair <strong className="text-slate-400">search + LLMs</strong> with enterprise
          knowledge bases. Prism sits in a similar problem space but emphasizes{" "}
          <strong className="text-slate-300">tenant-scoped RAG</strong>, <strong className="text-slate-300">auditable agent hops</strong>, and a{" "}
          <strong className="text-slate-300">path to federated adapter training</strong> without moving raw documents.
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-slate-800/90 bg-black/25 p-5">
            <h3 className="text-base font-semibold text-slate-100">
              <a
                href="https://www.hebbia.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal-300/95 underline decoration-teal-700/60 underline-offset-2 hover:text-teal-200"
              >
                Hebbia
              </a>
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              AI-native search and workflows over contracts, filings, and internal files — strong in legal and finance
              use cases where teams need fast answers across large document sets.
            </p>
          </div>
          <div className="rounded-xl border border-slate-800/90 bg-black/25 p-5">
            <h3 className="text-base font-semibold text-slate-100">
              <a
                href="https://www.alpha-sense.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal-300/95 underline decoration-teal-700/60 underline-offset-2 hover:text-teal-200"
              >
                AlphaSense
              </a>
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              Market intelligence and expert / broker research search — the reference stack for sell-side and
              corporate users who live in transcripts, models, and external research feeds.
            </p>
          </div>
        </div>
        <p className="mt-4 text-xs leading-relaxed text-slate-600">
          Prism is a hackathon-style reference implementation: not affiliated with the vendors above; names are for
          orientation only.
        </p>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-prism-panel/50 p-6 sm:p-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300/95">
          Beyond finance — agent workflows with privacy preserved
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-500">
          The same pattern — <strong className="text-slate-300">ingest → retrieve → multi-agent reasoning → quality gate</strong> — applies
          wherever experts need citations, contradiction checks, and strict data boundaries.
        </p>
        <ul className="mt-4 space-y-3 text-sm leading-relaxed text-slate-400">
          <li className="flex gap-3 border-b border-slate-800/60 pb-3 last:border-0 last:pb-0">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500/90" aria-hidden />
            <span>
              <strong className="text-slate-200">Legal & contracts</strong> — clause alignment across drafts, playbooks,
              and counterparty PDFs; privilege-sensitive workspaces per matter or client.
            </span>
          </li>
          <li className="flex gap-3 border-b border-slate-800/60 pb-3 last:border-0 last:pb-0">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500/90" aria-hidden />
            <span>
              <strong className="text-slate-200">Pharma & clinical ops</strong> — protocol and safety narrative consistency
              across CSR excerpts, labels, and internal medical review — often with stricter residency requirements than
              generic SaaS search.
            </span>
          </li>
          <li className="flex gap-3 border-b border-slate-800/60 pb-3 last:border-0 last:pb-0">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500/90" aria-hidden />
            <span>
              <strong className="text-slate-200">Insurance & underwriting</strong> — loss runs, submissions, and guidelines
              triaged into structured rationales with evidence spans for human sign-off.
            </span>
          </li>
          <li className="flex gap-3 border-b border-slate-800/60 pb-3 last:border-0 last:pb-0">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500/90" aria-hidden />
            <span>
              <strong className="text-slate-200">Public sector & procurement</strong> — RFPs, amendments, and policy
              memos compared under per-agency or per-program tenants so bid teams do not cross-contaminate corpora.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500/90" aria-hidden />
            <span>
              <strong className="text-slate-200">HR & internal policy</strong> — employee handbook, regional policy, and
              ticket history Q&amp;A with citations — ideal when only aggregate or federated feedback should leave the
              edge.
            </span>
          </li>
        </ul>
      </section>
    </div>
  );
}

/** Scoped copy of `prism_features_tab.html` — colors aligned with `tailwind` prism.bg / prism.panel / prism.accent. */
const PRISM_FEATURES_EMBED_CSS = `
.prism-features-embed,.prism-features-embed *{box-sizing:border-box}
.prism-features-embed{margin:0;padding:0;background:transparent;color:#e2e8f0;font-family:inherit}
.prism-features-embed .wrap{padding:2rem 1.5rem;max-width:960px;margin:0 auto}
.prism-features-embed .eyebrow{font-size:11px;letter-spacing:.12em;color:#5eead4;font-weight:500;text-align:center;margin-bottom:.75rem}
.prism-features-embed .headline{font-size:26px;font-weight:500;text-align:center;color:#f1f5f9;margin-bottom:.5rem}
.prism-features-embed .sub{font-size:14px;color:#94a3b8;text-align:center;max-width:560px;margin:0 auto 2rem}
.prism-features-embed .usps{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:1.75rem}
@media (max-width: 768px){.prism-features-embed .usps{grid-template-columns:1fr}}
.prism-features-embed .usp{background:rgb(18 26 47 / 0.75);border:1px solid rgb(51 65 85 / 0.55);border-radius:12px;padding:1.1rem 1.25rem}
.prism-features-embed .usp-label{font-size:11px;font-weight:500;letter-spacing:.1em;color:#5eead4;margin-bottom:.5rem}
.prism-features-embed .usp-title{font-size:14px;font-weight:500;color:#f1f5f9;margin-bottom:.4rem}
.prism-features-embed .usp-body{font-size:12px;color:#94a3b8;line-height:1.6}
.prism-features-embed .usp-body code{font-family:ui-monospace,SFMono-Regular,monospace;font-size:11px;background:#0b1020;padding:1px 4px;border-radius:4px;color:#7dd3fc;border:1px solid rgb(51 65 85 / 0.45)}
.prism-features-embed .grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
@media (max-width: 900px){.prism-features-embed .grid2{grid-template-columns:1fr}}
.prism-features-embed .card{background:rgb(18 26 47 / 0.75);border:1px solid rgb(51 65 85 / 0.55);border-radius:12px;padding:1.25rem}
.prism-features-embed .card-title{font-size:11px;font-weight:500;letter-spacing:.1em;color:#5eead4;margin-bottom:1rem}
.prism-features-embed .feat-list{list-style:none;display:flex;flex-direction:column;gap:.65rem;margin:0;padding:0}
.prism-features-embed .feat-list li{font-size:13px;color:#cbd5e1;line-height:1.5;display:flex;gap:8px;align-items:flex-start}
.prism-features-embed .feat-list li::before{content:"";width:6px;height:6px;border-radius:50%;background:#2dd4bf;margin-top:5px;flex-shrink:0}
.prism-features-embed .feat-list li strong{color:#f1f5f9;font-weight:500}
.prism-features-embed .feat-list li code{font-family:ui-monospace,SFMono-Regular,monospace;font-size:11px;background:#0b1020;padding:1px 5px;border-radius:4px;color:#7dd3fc;border:1px solid rgb(51 65 85 / 0.45)}
.prism-features-embed .pipeline{background:rgb(18 26 47 / 0.75);border:1px solid rgb(51 65 85 / 0.55);border-radius:12px;padding:1.25rem;margin-bottom:12px}
.prism-features-embed .pipe-title{font-size:11px;font-weight:500;letter-spacing:.1em;color:#5eead4;margin-bottom:1rem}
.prism-features-embed .pipe-row{display:flex;align-items:stretch;gap:0;flex-wrap:wrap}
.prism-features-embed .pipe-step{flex:1;min-width:140px;background:#0b1020;border:1px solid rgb(51 65 85 / 0.5);border-radius:8px;padding:.75rem .9rem;position:relative;margin-bottom:8px}
.prism-features-embed .pipe-step:not(:last-child){margin-right:28px}
@media (min-width: 901px){.prism-features-embed .pipe-step:not(:last-child)::after{content:"→";position:absolute;right:-20px;top:50%;transform:translateY(-50%);color:#475569;font-size:16px}}
.prism-features-embed .pipe-badge{display:inline-block;font-size:10px;font-weight:500;padding:2px 7px;border-radius:4px;margin-bottom:.4rem}
.prism-features-embed .badge-none{background:rgb(30 41 59 / 0.85);color:#7dd3fc;border:1px solid rgb(51 65 85 / 0.4)}
.prism-features-embed .badge-llm{background:rgb(49 46 129 / 0.45);color:#c4b5fd;border:1px solid rgb(99 102 241 / 0.35)}
.prism-features-embed .pipe-name{font-size:13px;font-weight:500;color:#f1f5f9;margin-bottom:.25rem}
.prism-features-embed .pipe-desc{font-size:11px;color:#94a3b8;line-height:1.5}
.prism-features-embed .tech-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:1rem}
.prism-features-embed .tech-pill{font-size:11px;font-weight:500;padding:4px 10px;border-radius:20px;border:1px solid rgb(51 65 85 / 0.55);color:#cbd5e1;background:#0b1020}
.prism-features-embed .tech-pill.teal{border-color:rgb(45 212 191 / 0.45);color:#5eead4;background:rgb(13 148 136 / 0.12)}
.prism-features-embed .oneliner{text-align:center;font-size:12px;color:#94a3b8;margin-top:1.25rem;padding-top:1.25rem;border-top:1px solid rgb(30 41 59 / 0.9)}
.prism-features-embed .oneliner em{color:#e2e8f0;font-style:normal}
`;

const PRISM_FEATURES_EMBED_HTML = `
<div class="wrap">
  <p class="eyebrow">PRISM FEATURES</p>
  <h1 class="headline">What Prism delivers</h1>
  <p class="sub">A governed, multi-tenant research stack: ingest your filings, retrieve with strict isolation, run agents to a thesis, and prove every claim — without mixing client data.</p>

  <div class="usps">
    <div class="usp">
      <div class="usp-label">USP 1</div>
      <div class="usp-title">Hard tenant boundaries</div>
      <div class="usp-body">Every run is scoped by <code>X-Prism-Tenant</code> and corpus. Retrieval never leaks across clients — enforced at the SQL layer.</div>
    </div>
    <div class="usp">
      <div class="usp-label">USP 2</div>
      <div class="usp-title">Evidence you can defend</div>
      <div class="usp-body">Hops, matrix, contradictions, and raw LLM traces — plus You.com web citations and regression checks on every output.</div>
    </div>
    <div class="usp">
      <div class="usp-label">USP 3</div>
      <div class="usp-title">Analyst-in-the-loop</div>
      <div class="usp-body">Thumbs + notes (PII-scrubbed server-side) feed local LoRA adapters via Flower federated learning — no raw data leaves the tenant.</div>
    </div>
  </div>

  <div class="pipeline">
    <div class="pipe-title">RESEARCH PIPELINE</div>
    <div class="pipe-row">
      <div class="pipe-step">
        <span class="pipe-badge badge-none">no LLM</span>
        <div class="pipe-name">Ingest</div>
        <div class="pipe-desc">PDFs, filings, transcripts, notes split into chunks and embedded into tenant-scoped pgvector index</div>
      </div>
      <div class="pipe-step">
        <span class="pipe-badge badge-none">no LLM</span>
        <div class="pipe-name">Research</div>
        <div class="pipe-desc">Embed query → vector search → rerank. Optionally merges You.com live results for external context</div>
      </div>
      <div class="pipe-step">
        <span class="pipe-badge badge-llm">LLM call 1</span>
        <div class="pipe-name">Analysis</div>
        <div class="pipe-desc">Single call extracts structured claims and detects contradictions across management statements vs. filings</div>
      </div>
      <div class="pipe-step">
        <span class="pipe-badge badge-llm">LLM call 2</span>
        <div class="pipe-name">Thesis</div>
        <div class="pipe-desc">Produces bull / bear / neutral thesis with mandatory chunk citations and confidence scores</div>
      </div>
    </div>
    <div class="tech-row">
      <span class="tech-pill teal">Ollama (local LLM)</span>
      <span class="tech-pill teal">You.com search</span>
      <span class="tech-pill teal">Google ADK orchestration</span>
      <span class="tech-pill teal">pgvector retrieval</span>
      <span class="tech-pill teal">MCP tool layer</span>
      <span class="tech-pill">2 LLM calls · ~20s p50</span>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <div class="card-title">MULTI-AGENT SYSTEM</div>
      <ul class="feat-list">
        <li><strong>Google ADK orchestration</strong> — structured multi-agent workflow with supervisor and quality gate</li>
        <li><strong>Research agent</strong> — retrieval only, zero LLM latency, strict tenant filter</li>
        <li><strong>Analysis agent</strong> — combined reasoning + contradiction detection in one LLM call</li>
        <li><strong>Thesis agent</strong> — structured bull / bear output with mandatory chunk-level citations</li>
        <li><strong>MCP tool layer</strong> — market intel, filings APIs, and external data sources pluggable without changing core agents</li>
        <li><strong>You.com integration</strong> — live web search merged into the research hop when <code>YOU_API_KEY</code> is set</li>
      </ul>
    </div>
    <div class="card">
      <div class="card-title">FEDERATED LEARNING</div>
      <ul class="feat-list">
        <li><strong>Flower FL server</strong> — aggregates LoRA adapter updates across tenants, never raw documents</li>
        <li><strong>Local PEFT trainer</strong> — analyst thumbs + edits train the reranker adapter on-device</li>
        <li><strong>Differential privacy</strong> — client updates are clipped and noised before leaving the tenant boundary</li>
        <li><strong>Secure aggregation</strong> — Flower SecAgg+ ensures the server never sees individual updates in the clear</li>
        <li><strong>Versioned adapter store</strong> — tenants evaluate and activate adapters locally; rollback is one click</li>
        <li><strong>Zero raw data sharing</strong> — only model deltas cross the tenant boundary, enforced architecturally</li>
      </ul>
    </div>
    <div class="card">
      <div class="card-title">GOVERNANCE & ACCESS</div>
      <ul class="feat-list">
        <li><strong>RBAC via principal header</strong> — roles for ingest, runs, evidence requests, and LLM profile admin</li>
        <li><strong>Restricted evidence references</strong> — cross-tenant discovery surfaces metadata only; content never leaks</li>
        <li><strong>Access request workflow</strong> — formal approve / deny / time-bound grants with full audit log</li>
        <li><strong>Quality gate</strong> — structured checks on thesis JSON before a run completes; blocks unsupported claims</li>
        <li><strong>Hop trace panel</strong> — every agent step, tool call, and LLM input / output visible for audit</li>
      </ul>
    </div>
    <div class="card">
      <div class="card-title">MODELS & INTEGRATIONS</div>
      <ul class="feat-list">
        <li><strong>Ollama (primary)</strong> — local open-source inference, no cloud dependency, strongest privacy story</li>
        <li><strong>LLM routing</strong> — per-tenant model profiles in Postgres; swap Mistral, Llama 3, Qwen without code changes</li>
        <li><strong>MCP server</strong> — pluggable market-intel tools; Veris MCP mount supported for packaged simulation</li>
        <li><strong>You.com</strong> — merged into the research hop for live external context when configured</li>
        <li><strong>Eval harness</strong> — regression suite on completed runs for CI-style quality gates</li>
      </ul>
    </div>
  </div>

  <div class="oneliner">One line for the deck: <em>"Prism is RAG + multi-agent reasoning with hard tenant isolation, You.com live search, MCP tools, and Flower federated learning — every claim is cited, every hop is auditable."</em></div>
</div>
`;

function PrismFeaturesPanel() {
  return (
    <div className="prism-features-embed mx-auto max-w-5xl rounded-2xl border border-slate-800 bg-prism-panel/50">
      <style dangerouslySetInnerHTML={{ __html: PRISM_FEATURES_EMBED_CSS }} />
      <div dangerouslySetInnerHTML={{ __html: PRISM_FEATURES_EMBED_HTML }} />
    </div>
  );
}

/** Demo-aligned FL “server” view — narrative matches Client Simulation tenants; not a live orchestrator UI. */
const FL_PARTICIPANTS = [
  {
    tenant: "frustrated_fran",
    workspace: "FranCloud (Frances)",
    ticker: "FRANCLOUD",
    localTrainer: "PEFT / LoRA on analyst-tagged spans",
    lastRound: "✓ submitted",
  },
  {
    tenant: "anxious_andy",
    workspace: "Meridian (Andrew)",
    ticker: "MERIDIAN",
    localTrainer: "PEFT / LoRA on analyst-tagged spans",
    lastRound: "✓ submitted",
  },
  {
    tenant: "cautious_carl",
    workspace: "Sable (Carl)",
    ticker: "SABLE",
    localTrainer: "PEFT / LoRA on analyst-tagged spans",
    lastRound: "✓ submitted",
  },
] as const;

type FLRunTenantId = (typeof FL_PARTICIPANTS)[number]["tenant"];

/** Dummy FL round logs (shape aligned with `fl-aggregates/round-1.txt`); per-tenant client slice + shared server merge. */
const FL_DUMMY_RUN_LOGS: Record<FLRunTenantId, Record<string, unknown>> = {
  frustrated_fran: {
    round_id: "fl-round-001",
    coordinator: "prism-fl-coordinator",
    seed: 42,
    tenant_id: "frustrated_fran",
    ticker: "FRANCLOUD",
    workspace: "FranCloud (Frances)",
    log_timestamp_utc: "2026-04-18T14:22:03.417Z",
    initial_global_adapter_w0: [0.0, 0.0],
    private_local_targets: {
      frustrated_fran: [1.0, 0.2],
    },
    hyperparameters: {
      local_lr: 0.5,
      noise_scale: 0.02,
      sample_counts: { frustrated_fran: 120 },
      clip_norm_l2: 1.0,
      dp_epsilon_round: 4.2,
      secure_agg: "SecAgg+ (design)",
    },
    client_updates_after_fit: {
      frustrated_fran: {
        w_prime: [0.5099342830602247, 0.0972347139765763],
        noise_draw: [0.009934283060224654, -0.002765286023423693],
        l2_delta: 0.5538912,
      },
    },
    server_aggregation: {
      method: "FedAvg",
      formula_weighted: "(n_fran*w_fran + n_andy*w_andy + n_carl*w_carl) / (n_fran+n_andy+n_carl)",
      contributing_clients: ["frustrated_fran", "anxious_andy", "cautious_carl"],
      sample_counts_all: { frustrated_fran: 120, anxious_andy: 95, cautious_carl: 110 },
      aggregated_w_sample_weighted: [0.4210431437756733, 0.455432312550909],
      quorum_met: true,
      round_status: "committed",
    },
    privacy_note:
      "Only low-dimensional adapter tensors leave the client in this toy; raw corpus documents never enter the aggregation step.",
  },
  anxious_andy: {
    round_id: "fl-round-001",
    coordinator: "prism-fl-coordinator",
    seed: 42,
    tenant_id: "anxious_andy",
    ticker: "MERIDIAN",
    workspace: "Meridian (Andrew)",
    log_timestamp_utc: "2026-04-18T14:22:04.903Z",
    initial_global_adapter_w0: [0.0, 0.0],
    private_local_targets: {
      anxious_andy: [0.55, 0.78],
    },
    hyperparameters: {
      local_lr: 0.5,
      noise_scale: 0.02,
      sample_counts: { anxious_andy: 95 },
      clip_norm_l2: 1.0,
      dp_epsilon_round: 4.2,
      secure_agg: "SecAgg+ (design)",
    },
    client_updates_after_fit: {
      anxious_andy: {
        w_prime: [0.4128841193847656, 0.6182903343439083],
        noise_draw: [0.007884119384765625, -0.02170966565609169],
        l2_delta: 0.74400255,
      },
    },
    server_aggregation: {
      method: "FedAvg",
      formula_weighted: "(n_fran*w_fran + n_andy*w_andy + n_carl*w_carl) / (n_fran+n_andy+n_carl)",
      contributing_clients: ["frustrated_fran", "anxious_andy", "cautious_carl"],
      sample_counts_all: { frustrated_fran: 120, anxious_andy: 95, cautious_carl: 110 },
      aggregated_w_sample_weighted: [0.4210431437756733, 0.455432312550909],
      quorum_met: true,
      round_status: "committed",
    },
    privacy_note:
      "Only low-dimensional adapter tensors leave the client in this toy; raw corpus documents never enter the aggregation step.",
  },
  cautious_carl: {
    round_id: "fl-round-001",
    coordinator: "prism-fl-coordinator",
    seed: 42,
    tenant_id: "cautious_carl",
    ticker: "SABLE",
    workspace: "Sable (Carl)",
    log_timestamp_utc: "2026-04-18T14:22:06.081Z",
    initial_global_adapter_w0: [0.0, 0.0],
    private_local_targets: {
      cautious_carl: [0.38, 0.85],
    },
    hyperparameters: {
      local_lr: 0.5,
      noise_scale: 0.02,
      sample_counts: { cautious_carl: 110 },
      clip_norm_l2: 1.0,
      dp_epsilon_round: 4.2,
      secure_agg: "SecAgg+ (design)",
    },
    client_updates_after_fit: {
      cautious_carl: {
        w_prime: [0.33111742198467373, 0.7055432194471359],
        noise_draw: [0.02111742198467373, 0.005543219447135925],
        l2_delta: 0.7794411,
      },
    },
    server_aggregation: {
      method: "FedAvg",
      formula_weighted: "(n_fran*w_fran + n_andy*w_andy + n_carl*w_carl) / (n_fran+n_andy+n_carl)",
      contributing_clients: ["frustrated_fran", "anxious_andy", "cautious_carl"],
      sample_counts_all: { frustrated_fran: 120, anxious_andy: 95, cautious_carl: 110 },
      aggregated_w_sample_weighted: [0.4210431437756733, 0.455432312550909],
      quorum_met: true,
      round_status: "committed",
    },
    privacy_note:
      "Only low-dimensional adapter tensors leave the client in this toy; raw corpus documents never enter the aggregation step.",
  },
};

function ServerAnalysisPanel() {
  const [runLogTenant, setRunLogTenant] = useState<FLRunTenantId>("frustrated_fran");

  return (
    <div className="mx-auto max-w-5xl space-y-10">
      <header className="text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-400/90">Server analysis</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
          Federated learning — aggregation plane
        </h1>
        <p className="mx-auto mt-4 max-w-3xl text-sm leading-relaxed text-slate-400">
          How a coordination server would treat the <strong className="text-slate-300">same three demo tenants</strong>{" "}
          you open under Client Simulation: who trains locally, what gets uploaded, and how rounds are merged. This
          page is a <span className="text-slate-300">design snapshot</span> for judges and operators — the live API
          today runs tenant-isolated RAG + quality gates; a production Flower / FedML-style coordinator would sit
          alongside it.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-800 bg-prism-panel/50 p-6 sm:p-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300/95">Participating clients</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-500">
          Clients that opted into the current training cohort. Each row is a separate <code className="text-slate-400">tenant_id</code>{" "}
          with its own corpus and local adapter — aligned with seeded workspaces.
        </p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800/80">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-black/25 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3 font-medium">Tenant</th>
                <th className="px-4 py-3 font-medium">Workspace</th>
                <th className="px-4 py-3 font-medium">Ticker</th>
                <th className="px-4 py-3 font-medium">Local trainer</th>
                <th className="px-4 py-3 font-medium">Round t</th>
              </tr>
            </thead>
            <tbody>
              {FL_PARTICIPANTS.map((c) => (
                <tr key={c.tenant} className="border-b border-slate-800/90 text-slate-300">
                  <td className="px-4 py-3 font-mono text-xs text-teal-200/90">{c.tenant}</td>
                  <td className="px-4 py-3">{c.workspace}</td>
                  <td className="px-4 py-3 font-mono text-xs">{c.ticker}</td>
                  <td className="px-4 py-3 text-slate-400">{c.localTrainer}</td>
                  <td className="px-4 py-3 text-emerald-400/90">{c.lastRound}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-slate-600">
          Eligibility: analyst thumbs + optional note pass PII scrub; only clips with governance labels enter the local
          gradient. Clients can drop out per round without blocking others (stale weights excluded from mean).
        </p>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-prism-panel/50 p-6 sm:p-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300/95">Dummy round run log</h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">
              Static snapshot for <code className="text-slate-400">fl-round-001</code> — same field style as{" "}
              <code className="text-slate-400">fl-aggregates/round-1.txt</code> (seed, targets, hyperparameters, client
              tensors, FedAvg merge). Each tenant shows its local slice plus the shared server aggregation line.
            </p>
          </div>
          <div className="shrink-0">
            <label htmlFor="fl-run-log-tenant" className="sr-only">
              Tenant run log
            </label>
            <select
              id="fl-run-log-tenant"
              value={runLogTenant}
              onChange={(e) => setRunLogTenant(e.target.value as FLRunTenantId)}
              className="w-full min-w-[220px] rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2 text-sm text-slate-200 outline-none ring-teal-600/40 focus:ring-2 sm:w-auto"
            >
              {FL_PARTICIPANTS.map((c) => (
                <option key={c.tenant} value={c.tenant}>
                  {c.workspace} ({c.tenant})
                </option>
              ))}
            </select>
          </div>
        </div>
        <pre
          className="mt-4 max-h-[min(520px,55vh)] overflow-auto rounded-xl border border-slate-800/90 bg-black/40 p-4 text-left font-mono text-[11px] leading-relaxed text-slate-300 [tab-size:2]"
          tabIndex={0}
        >
          {JSON.stringify(FL_DUMMY_RUN_LOGS[runLogTenant], null, 2)}
        </pre>
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-2xl border border-slate-800 bg-prism-panel/40 p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300/95">Aggregation</h2>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm leading-relaxed text-slate-400 marker:text-teal-600">
            <li>
              <strong className="text-slate-300">FedAvg-style</strong> mean over client LoRA deltas (same rank + base
              checkpoint), weighted by scrubbed token count per client.
            </li>
            <li>
              <strong className="text-slate-300">Quorum:</strong> minimum 2 of 3 clients for a round to commit; else
              server holds global state and retries next window.
            </li>
            <li>
              <strong className="text-slate-300">Outlier drop:</strong> cosine distance to round median above threshold
              → flag for manual review (no merge until cleared).
            </li>
            <li>
              <strong className="text-slate-300">Secure aggregation + differential privacy:</strong>{" "}
              pairwise-masked uploads so no party sees another client&apos;s raw delta; after unmasking the sum, the
              server applies <strong className="text-slate-300">differential privacy</strong> (calibrated noise on the
              aggregate update, with an explicit (ε, δ) budget per round) before publishing the global adapter.
            </li>
          </ul>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-prism-panel/40 p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300/95">What leaves the client</h2>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm leading-relaxed text-slate-400 marker:text-teal-600">
            <li>Low-rank adapter weights only — <strong className="text-slate-300">no</strong> raw filings, transcripts, or free-text notes.</li>
            <li>Gradient clipping + noise budget tied to analyst-approved clip volume (privacy accounting).</li>
            <li>Metadata: <code className="text-slate-500">round_id</code>, <code className="text-slate-500">tenant_id</code>,{" "}
              <code className="text-slate-500">sample_hash</code> (opaque), optional DP epsilon used.</li>
            <li>Server stores aggregated global adapter + per-round audit log; per-client deltas discarded post-merge.</li>
          </ul>
        </section>
      </div>

      <section className="rounded-2xl border border-slate-800 bg-prism-panel/40 p-6 sm:p-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-300/95">Server responsibilities</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-800/80 bg-black/20 p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Orchestration</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              Issue round keys, version base models, collect uploads, enforce timeouts, broadcast new global adapter
              revision.
            </p>
          </div>
          <div className="rounded-xl border border-slate-800/80 bg-black/20 p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Validation</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              Schema checks on delta tensors, shape match to LoRA config, replay on public eval harness before merge.
            </p>
          </div>
          <div className="rounded-xl border border-slate-800/80 bg-black/20 p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Observability</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              Per-tenant participation rate, drift vs. prior global, cross-client loss on shared red-team prompts (no
              client data).
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-amber-900/35 bg-amber-950/15 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-200/95">Linked to Prism workspace</h2>
        <p className="mt-2 text-sm leading-relaxed text-amber-100/85">
          Evidence-access requests and <strong className="text-amber-50/95">cross-tenant retrieval</strong> stay under
          governance in the product UI; federated training is orthogonal — it improves shared adapters using{" "}
          <em>labeled</em> local signal, not by pooling another client&apos;s corpus. Server analysis here describes the
          training coordinator; use <strong className="text-amber-50/95">Client Simulation</strong> for per-tenant RAG
          isolation demos.
        </p>
      </section>
    </div>
  );
}

export default function DemoLanding() {
  const [activeTab, setActiveTab] = useState<NavTabId>("client_simulation");

  return (
    <div className="prism-landing flex min-h-dvh flex-col bg-prism-bg text-slate-100">
      <nav className="sticky top-0 z-20 border-b border-slate-800/90 bg-prism-bg/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-1 px-4 py-2 sm:gap-2 sm:px-6">
          <Link
            href="/"
            className="mr-2 shrink-0 text-lg font-semibold tracking-tight text-teal-300 hover:text-teal-200 sm:mr-4"
          >
            Prism
          </Link>
          <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-1 sm:justify-start sm:gap-1.5">
            {NAV_TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`rounded-lg px-2.5 py-2 text-left text-[11px] font-medium leading-tight transition sm:px-3 sm:text-xs ${
                  activeTab === t.id
                    ? "bg-teal-900/50 text-teal-100 ring-1 ring-teal-600/40"
                    : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <div className="flex-1">
        <div
          className={`mx-auto px-6 py-10 sm:py-14 ${
            activeTab === "server_analysis" ||
            activeTab === "features" ||
            activeTab === "system_design" ||
            activeTab === "use_cases"
              ? "max-w-6xl"
              : "max-w-4xl"
          }`}
        >
          {activeTab === "features" && <PrismFeaturesPanel />}
          {activeTab === "use_cases" && <ApplicabilityPanel />}
          {activeTab === "server_analysis" && <ServerAnalysisPanel />}
          {activeTab === "system_design" && <SystemDesignDiagram />}

          {activeTab === "client_simulation" && (
            <>
              <header className="mb-12 text-center">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-400/90">Prism demo</p>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-50 sm:text-4xl">
                  Choose a client workspace
                </h1>
                <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-slate-400">
                  Each persona uses a separate <span className="font-mono text-slate-300">X-Prism-Tenant</span> and its
                  own ingested corpus (earnings + filing + internal note). Open one to show side-by-side isolation: the
                  left corpus list and retrieval never mix between clients.
                </p>
              </header>

              <ul className="grid gap-5 sm:grid-cols-1 md:grid-cols-3">
                {personas.map((p) => (
                  <li key={p.slug}>
                    <Link
                      href={workspaceHref(p)}
                      className={`flex h-full flex-col rounded-2xl border bg-gradient-to-b p-5 shadow-lg transition hover:brightness-110 hover:ring-2 hover:ring-teal-500/30 ${p.accent}`}
                    >
                      <span className="text-balance text-base font-semibold leading-snug text-white sm:text-lg">
                        {p.name}
                      </span>
                      <span className="mt-2 text-[11px] leading-relaxed text-teal-200/90">
                        <span className="font-mono">tenant={p.slug}</span>
                        <span className="text-teal-100/70"> · </span>
                        <span className="font-semibold text-teal-100">{p.company}</span>
                        <span className="text-teal-100/70"> · ticker </span>
                        <span className="font-mono">{p.ticker}</span>
                      </span>
                      <p className="mt-3 flex-1 text-sm leading-snug text-slate-300">{p.tagline}</p>
                      <span className="mt-5 inline-flex items-center text-sm font-medium text-teal-300">
                        Open workspace →
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>

              <div className="mt-14 flex flex-col items-center gap-4 border-t border-slate-800 pt-10 text-center">
                <Link
                  href="/workspace"
                  className="text-sm text-teal-400/90 underline decoration-teal-600/50 underline-offset-4 hover:text-teal-300"
                >
                  Custom workspace (set tenant & company ticker yourself)
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
