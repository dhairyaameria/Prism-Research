function Box({
  title,
  sub,
  className = "",
}: {
  title: string;
  sub?: string;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border px-2.5 py-2 text-center shadow-sm ${className}`}
    >
      <div className="text-[11px] font-semibold leading-tight text-slate-100 sm:text-xs">{title}</div>
      {sub ? <div className="mt-1 text-[9px] leading-snug text-slate-400 sm:text-[10px]">{sub}</div> : null}
    </div>
  );
}

function Arrow({ label }: { label?: string }) {
  return (
    <span className="flex shrink-0 items-center justify-center px-0.5 text-slate-600" aria-hidden>
      {label ?? "→"}
    </span>
  );
}

function PartnerBadge({
  href,
  src,
  label,
}: {
  href: string;
  src: string;
  label: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center rounded-lg border border-slate-600/80 bg-slate-900/70 p-1.5 ring-1 ring-slate-700/50 transition hover:border-teal-700/60 hover:ring-teal-800/40"
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- small local SVG wordmarks */}
      <img src={src} alt={label} width={100} height={28} className="h-7 w-auto" />
    </a>
  );
}

export default function SystemDesignDiagram() {
  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header className="text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-400/90">Architecture design</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
          Prism — layered system view
        </h1>
        <p className="mx-auto mt-3 max-w-3xl text-sm leading-relaxed text-slate-400">
          Bank-style <strong className="text-slate-300">tenant boundary</strong> around data and models, with a
          federated learning strip below. Boxes reflect <em>current</em> implementation choices in this repo (not only
          the original sketch).
        </p>
      </header>

      {/* Client plane */}
      <section className="rounded-2xl border-2 border-dashed border-violet-600/45 bg-violet-950/15 p-4 sm:p-5">
        <h2 className="mb-3 text-center text-[10px] font-bold uppercase tracking-[0.18em] text-violet-300/95">
          Client plane
        </h2>
        <div className="flex flex-wrap items-stretch justify-center gap-2 sm:gap-3">
          <Box
            title="Analyst web app"
            sub="Next.js · landing + /workspace"
            className="min-w-[140px] flex-1 border-violet-700/50 bg-violet-950/35"
          />
          <Box
            title="Chat + corpus"
            sub="Tenant + ticker · ingest"
            className="min-w-[140px] flex-1 border-violet-700/50 bg-violet-950/35"
          />
          <Box
            title="Run details drawer"
            sub="Hops · Matrix · Tensions · Cross reference"
            className="min-w-[160px] flex-1 border-violet-700/50 bg-violet-950/35"
          />
        </div>
        <p className="mt-3 text-center text-[10px] leading-relaxed text-violet-200/70">
          <strong className="text-violet-100/90">Design update:</strong> cross-tenant tools live under{" "}
          <em>Cross reference</em> in the drawer (not the sidebar). Hops show <em>raw LLM JSON</em> for Analysis &
          Thesis.
        </p>
      </section>

      {/* Tenant data plane */}
      <section className="rounded-2xl border-2 border-dashed border-slate-500/50 bg-slate-900/20 p-4 sm:p-6">
        <h2 className="mb-4 text-center text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
          Tenant data plane — bank boundary
        </h2>

        <div className="mb-4 flex flex-wrap items-center justify-center gap-1">
          <Box
            title="FastAPI gateway"
            sub="Auth · X-Prism-Tenant · SSE runs"
            className="min-w-[120px] border-emerald-700/55 bg-emerald-950/35"
          />
          <Arrow />
          <Box
            title="Pipeline router"
            sub="PRISM_PIPELINE: fast vs ADK"
            className="min-w-[120px] border-emerald-700/55 bg-emerald-950/35"
          />
          <Arrow />
          <Box
            title="Quality gate"
            sub="Thesis JSON checks · pass/fail"
            className="min-w-[120px] border-emerald-700/55 bg-emerald-950/35"
          />
        </div>

        <div className="mb-4 flex flex-wrap items-center justify-center gap-1">
          <Box title="Research" sub="Retrieve + You.com merge" className="min-w-[88px] border-emerald-700/50 bg-emerald-950/30" />
          <Arrow />
          <Box title="Analysis" sub="LLM · claims + tensions" className="min-w-[88px] border-emerald-700/50 bg-emerald-950/30" />
          <Arrow />
          <Box title="Thesis" sub="LLM · stance + matrix" className="min-w-[88px] border-emerald-700/50 bg-emerald-950/30" />
          <span className="mx-1 text-slate-600">|</span>
          <Box
            title="ADK chain (alt.)"
            sub="Research→Reasoning→…"
            className="min-w-[120px] border-emerald-800/40 bg-emerald-950/20"
          />
        </div>

        <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Box title="Evidence flow" sub="Claims · contradictions · matrix rows" className="border-amber-800/55 bg-amber-950/25" />
          <Box title="Hop persistence" sub="JSON payloads · llm_response_text" className="border-amber-800/55 bg-amber-950/25" />
          <Box title="Citations" sub="Internal + You.com metadata" className="border-amber-800/55 bg-amber-950/25" />
          <Box title="RBAC" sub="Principal · roles · evidence requests" className="border-amber-800/55 bg-amber-950/25" />
        </div>

        <div className="grid gap-3 lg:grid-cols-12">
          <div className="lg:col-span-5 space-y-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-sky-400/90">Retrieval</h3>
            <div className="flex flex-wrap items-center gap-1">
              <Box title="Ingest" sub="Text + PDF" className="min-w-[72px] border-sky-700/50 bg-sky-950/35" />
              <Arrow />
              <Box title="Chunk + embed" sub="pgvector 384d" className="min-w-[88px] border-sky-700/50 bg-sky-950/35" />
              <Arrow />
              <Box title="Hybrid search" sub="Tenant + ticker scope" className="min-w-[96px] border-sky-700/50 bg-sky-950/35" />
            </div>
            <Box title="Postgres" sub="documents · chunks · hops · runs" className="border-sky-800/40 bg-sky-950/20" />
          </div>

          <div className="lg:col-span-4 flex flex-col items-center justify-center gap-2 rounded-xl border border-fuchsia-800/40 bg-fuchsia-950/15 p-3">
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-fuchsia-300/90">External intelligence</h3>
            <div className="flex flex-wrap items-center justify-center gap-2">
              <PartnerBadge href="https://you.com/platform" src="/brands/youcom.svg" label="You.com" />
              <Box title="MCP" sub="market-intel tools" className="min-w-[100px] border-fuchsia-700/45 bg-fuchsia-950/30" />
              <PartnerBadge href="https://veris.ai" src="/brands/veris.svg" label="Veris AI" />
            </div>
            <p className="text-center text-[9px] text-fuchsia-200/70">You.com in fast research hop; Veris optional MCP mount.</p>
          </div>

          <div className="lg:col-span-3 flex flex-col justify-center gap-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-rose-300/90">Model runtime</h3>
            <Box
              title="Tenant LLM profile"
              sub="Postgres row → env-resolved keys"
              className="border-rose-800/50 bg-rose-950/30"
            />
            <div className="flex justify-center">
              <PartnerBadge href="https://www.baseten.co" src="/brands/baseten.svg" label="Baseten" />
            </div>
            <p className="text-center text-[9px] text-rose-200/65">Default path: Baseten OpenAI-compatible; Ollama / Gemini supported.</p>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-rose-800/35 bg-rose-950/15 p-3 text-center">
          <Box
            title="Governed cross-tenant access"
            sub="POST evidence-access-requests · subject tenant + ticker"
            className="mx-auto max-w-md border-rose-700/45 bg-rose-950/25"
          />
        </div>

        <div className="mt-4 rounded-xl border border-dashed border-violet-600/40 bg-violet-950/15 p-3">
          <h3 className="text-center text-[10px] font-bold uppercase tracking-wide text-violet-300/90">
            Local learning layer (client story)
          </h3>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-1">
            <Box title="Analyst feedback" sub="Thumbs + note · PII scrub" className="min-w-[110px] border-violet-700/45 bg-violet-950/30" />
            <Arrow />
            <Box title="Boundary signals" sub="bundle.local_learning" className="min-w-[120px] border-violet-700/45 bg-violet-950/30" />
            <Arrow />
            <Box title="Cross ref. UI" sub="Drawer tab when eligible" className="min-w-[110px] border-violet-700/45 bg-violet-950/30" />
          </div>
        </div>
      </section>

      {/* Federated plane */}
      <section className="rounded-2xl border-2 border-dashed border-violet-600/45 bg-violet-950/15 p-4 sm:p-5">
        <h2 className="mb-3 text-center text-[10px] font-bold uppercase tracking-[0.18em] text-violet-300/95">
          Federated learning plane
        </h2>
        <div className="flex flex-wrap items-center justify-center gap-1">
          <Box title="Flower client (demo)" sub="Per-tenant · apps/fl_stretch" className="min-w-[120px] border-violet-700/50 bg-violet-950/35" />
          <Arrow />
          <Box title="Secure aggregation" sub="+ DP on aggregate (design)" className="min-w-[130px] border-violet-700/50 bg-violet-950/35" />
          <Arrow />
          <Box title="Aggregator server" sub="FedAvg-style merge" className="min-w-[120px] border-violet-700/50 bg-violet-950/35" />
          <Arrow />
          <Box title="Adapter store" sub="Versioned LoRA / PEFT" className="min-w-[120px] border-violet-700/50 bg-violet-950/35" />
        </div>
        <p className="mt-3 text-center text-[10px] text-violet-200/75">
          Narrative on <strong className="text-violet-100/90">Server Analysis</strong> tab; coordinator not wired to live API runs.
        </p>
      </section>

      <aside className="rounded-xl border border-slate-700 bg-slate-950/50 p-4 text-sm leading-relaxed text-slate-400">
        <span className="font-semibold text-slate-200">Design deltas vs. a generic RAG diagram:</span> per-tenant LLM
        profiles; You.com rows and <code className="text-slate-500">you_com</code> labels in the matrix; raw LLM text
        stored on Analysis/Thesis hops; cross-tenant workflow in Run details only; <code className="text-slate-500">local_learning</code>{" "}
        in API bundles for gating; evidence requests carry subject tenant/ticker.
      </aside>
    </div>
  );
}
