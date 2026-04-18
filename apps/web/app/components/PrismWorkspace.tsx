"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

const API =
  typeof process.env.NEXT_PUBLIC_API_URL === "string" && process.env.NEXT_PUBLIC_API_URL.trim() !== ""
    ? process.env.NEXT_PUBLIC_API_URL.trim().replace(/\/$/, "")
    : "/api/prism";

async function responseJson<T>(r: Response): Promise<
  { ok: true; data: T } | { ok: false; status: number; body: string }
> {
  const body = await r.text();
  if (!r.ok) {
    let msg = body.slice(0, 1200);
    try {
      const err = JSON.parse(body) as { detail?: unknown };
      if (typeof err.detail === "string") msg = err.detail;
      else if (err.detail != null) msg = JSON.stringify(err.detail);
    } catch {
      /* ignore */
    }
    return { ok: false, status: r.status, body: msg };
  }
  try {
    return { ok: true, data: JSON.parse(body) as T };
  } catch {
    return {
      ok: false,
      status: r.status,
      body: `invalid JSON (${body.slice(0, 120)}${body.length > 120 ? "…" : ""})`,
    };
  }
}

type IntegrationStatus = {
  tenant_id?: string;
  llm: {
    provider?: string;
    baseten_only?: boolean;
    model_id: string;
    model_config_warning?: string | null;
    chat_via?: string;
    route?: string;
    ollama?: boolean;
    ollama_base?: string | null;
    google_gemini_configured: boolean;
  };
  you_com: { search_configured: boolean };
  veris: { fastapi_mcp_mount: boolean; template: string };
};

type LocalLearningSignals = {
  suggest_team_boundary_request: boolean;
  confidence: number;
  signals: string[];
  retrieval_summary?: { vector_chunks: number | null; you_com_chunks: number | null };
  narrative?: string;
};

type Bundle = {
  run: {
    id: string;
    tenant_id?: string;
    ticker: string;
    question: string;
    status: string;
    thesis_json: Record<string, unknown> | null;
    quality_passed?: boolean | null;
    quality_report?: Record<string, unknown> | null;
    replay_of?: string | null;
  };
  hops: { id: string; agent: string; intent: string | null; payload: unknown; duration_ms: number | null }[];
  matrix_rows: {
    theme: string;
    summary: string | null;
    confidence: number | null;
    evidence: string | null;
    citation_ids: unknown;
  }[];
  contradictions: {
    tension_type: string | null;
    description: string;
    side_a: unknown;
    side_b: unknown;
  }[];
  /** Federated-style client signal: thin retrieval / quality / matrix → optional evidence-access UX. */
  local_learning?: LocalLearningSignals;
};

type CorpusDoc = {
  id: string;
  title: string;
  source_kind: string;
  created_at: string | null;
  chunk_count: number;
};

type ChatMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      bundle: Bundle | null;
      loading: boolean;
      phase?: string;
      evalResult?: Record<string, unknown> | null;
      qualityPassed?: boolean | null;
      qualityReport?: Record<string, unknown> | null;
    };

const PRISM_MEMORY_VERSION = 1 as const;

type PrismMemoryBlob = {
  v: typeof PRISM_MEMORY_VERSION;
  messages: ChatMessage[];
  questionDraft: string;
  feedbackNote: string;
  manualAccessTools: boolean;
  updatedAt: number;
};

function prismSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = sessionStorage.getItem("prism_session_id");
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem("prism_session_id", id);
  }
  return id;
}

function prismMemoryStorageKey(sessionId: string, tenant: string, ticker: string): string {
  return `prism_memory_v${PRISM_MEMORY_VERSION}_${sessionId}_${encodeURIComponent(tenant)}_${encodeURIComponent(ticker)}`;
}

function normalizePersistedMessages(raw: unknown): ChatMessage[] {
  if (!Array.isArray(raw)) return [];
  const out: ChatMessage[] = [];
  for (const m of raw) {
    if (!m || typeof m !== "object") continue;
    const o = m as Record<string, unknown>;
    if (o.role === "user" && typeof o.id === "string" && typeof o.content === "string") {
      out.push({ id: o.id, role: "user", content: o.content });
      continue;
    }
    if (o.role === "assistant" && typeof o.id === "string") {
      out.push({
        id: o.id,
        role: "assistant",
        content: typeof o.content === "string" ? o.content : "",
        bundle: (o.bundle as Bundle | null | undefined) ?? null,
        loading: false,
        phase: undefined,
        evalResult: (o.evalResult as Record<string, unknown> | null | undefined) ?? null,
        qualityPassed: typeof o.qualityPassed === "boolean" ? o.qualityPassed : null,
        qualityReport: (o.qualityReport as Record<string, unknown> | null | undefined) ?? null,
      });
    }
  }
  return out;
}

function messagesForStorage(messages: ChatMessage[]): ChatMessage[] {
  return messages.filter((m) => m.role !== "assistant" || !m.loading);
}

type DrawerTab = "hops" | "matrix" | "contradictions" | "cross_reference";

/** Seeded demo clients — match `scripts/seed_demo_clients.py` tenant_ids. */
const DEMO_CLIENT_NAMES: Record<string, string> = {
  frustrated_fran: 'Frustrated Frances ',
  anxious_andy: "Anxious Andrew",
  cautious_carl: "Cautious Carl",
};

const DEFAULT_DEMO_PRINCIPAL = "demo@prism.local";

/** Demo workspaces (tenant + company ticker) for cross-client flows. */
const DEMO_WORKSPACES = [
  { tenant: "frustrated_fran", ticker: "FRANCLOUD", label: "FranCloud (Frances)" },
  { tenant: "anxious_andy", ticker: "MERIDIAN", label: "Meridian (Andrew)" },
  { tenant: "cautious_carl", ticker: "SABLE", label: "Sable (Carl)" },
] as const;

/** Suggested questions whose *answers* mainly live in another tenant's corpus (demo isolation story). */
const CROSS_CLIENT_HINTS: Partial<
  Record<string, { question: string; answerHint: string; subjectTenant: string; subjectTicker: string }[]>
> = {
  frustrated_fran: [
    {
      question:
        "Quantify the DOJ voluntary inquiry, legal reserve, and any going-concern language in our disclosures.",
      answerHint: "That narrative is seeded under Meridian (Andrew) — not in this FranCloud corpus.",
      subjectTenant: "anxious_andy",
      subjectTicker: "MERIDIAN",
    },
    {
      question:
        "How does customer acceptance testing defer revenue for large tools, and what did we say about fab timing slippage?",
      answerHint: "Seeded under Sable (Carl) — different tenant from FranCloud.",
      subjectTenant: "cautious_carl",
      subjectTicker: "SABLE",
    },
  ],
  anxious_andy: [
    {
      question:
        "Reconcile NPS decline, support ticket spike, and UI refresh risks with management's satisfaction commentary.",
      answerHint: "Seeded under FranCloud (Frances) — not in Meridian's ingested docs.",
      subjectTenant: "frustrated_fran",
      subjectTicker: "FRANCLOUD",
    },
    {
      question:
        "What inventory reserve and revenue-recognition caveats apply to legacy product lines?",
      answerHint: "Seeded under Sable (Carl).",
      subjectTenant: "cautious_carl",
      subjectTicker: "SABLE",
    },
  ],
  cautious_carl: [
    {
      question:
        "What are the macro, DOJ, and liquidity stress-test disclosures for our freight marketplace?",
      answerHint: "Seeded under Meridian (Andrew).",
      subjectTenant: "anxious_andy",
      subjectTicker: "MERIDIAN",
    },
    {
      question:
        "What does the 10-Q say about UI-driven churn and competitor pricing vs. transcript optimism?",
      answerHint: "Seeded under FranCloud (Frances).",
      subjectTenant: "frustrated_fran",
      subjectTicker: "FRANCLOUD",
    },
  ],
};

function thesisNarrative(thesis: Record<string, unknown> | undefined): string {
  if (!thesis) return "";
  return typeof thesis.narrative === "string" ? thesis.narrative : "";
}

function thesisStance(thesis: Record<string, unknown> | undefined): string {
  if (!thesis) return "";
  const s = thesis.stance;
  return typeof s === "string" ? s.toUpperCase() : "";
}

export default function PrismWorkspace() {
  const searchParams = useSearchParams();

  const [ticker, setTicker] = useState("DEMO");
  const [transcript, setTranscript] = useState(
    "CEO: We delivered strong ARR growth and improved operating leverage. CFO: We expect margins to normalize next year as we reinvest.",
  );
  const [filing, setFiling] = useState(
    "Risk factors: Our gross margin expansion may not be sustainable beyond the next two quarters due to competitive pricing pressure.",
  );
  const [questionDraft, setQuestionDraft] = useState(
    "What changed this quarter, and what risks contradict management tone?",
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);
  const [tenant, setTenant] = useState("default");
  const [principal, setPrincipal] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedbackNote, setFeedbackNote] = useState("");
  const [corpusDocs, setCorpusDocs] = useState<CorpusDoc[]>([]);
  const [corpusLoading, setCorpusLoading] = useState(false);
  const [corpusError, setCorpusError] = useState<string | null>(null);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawer, setDrawer] = useState<{ bundle: Bundle; tab: DrawerTab } | null>(null);
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [evidenceTargetKey, setEvidenceTargetKey] = useState<string>("");
  const [evidenceNote, setEvidenceNote] = useState("");
  const [evidenceStatus, setEvidenceStatus] = useState<string | null>(null);
  /** Demo only: unlock cross-reference tools in Run details for this session. */
  const [manualAccessTools, setManualAccessTools] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const corpusFetchGen = useRef(0);
  const persistDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Bumped after storage hydrate so debounced persist re-runs with restored messages. */
  const [memoryTick, setMemoryTick] = useState(0);

  const demoClientLabel = DEMO_CLIENT_NAMES[tenant] ?? null;

  const prevWorkspaceKey = useRef<string | null>(null);

  /** Apply URL → state before paint so corpus / API calls never use stale default/DEMO on first fetch. */
  useLayoutEffect(() => {
    const tp = searchParams.get("tenant")?.trim();
    const tick = searchParams.get("ticker")?.trim();
    const pr = searchParams.get("principal");
    const q = searchParams.get("question");

    if (tp) setTenant(tp);
    if (tick) setTicker(tick.toUpperCase());

    if (pr !== null) setPrincipal(pr);
    else if (tp && DEMO_CLIENT_NAMES[tp]) setPrincipal(DEFAULT_DEMO_PRINCIPAL);

    if (q?.trim()) setQuestionDraft(q.trim());

    if (tp && DEMO_CLIENT_NAMES[tp]) {
      setTranscript("");
      setFiling("");
    }
  }, [searchParams.toString()]);

  /** Per browser-tab session + workspace: load saved chat / draft from localStorage. */
  useEffect(() => {
    if (typeof window === "undefined") return;
    const sid = prismSessionId();
    const ws = `${tenant}:${ticker}`;
    const storeKey = prismMemoryStorageKey(sid, tenant, ticker);
    const urlQuestionOnLoad = searchParams.get("question")?.trim();

    const hydrateFromStorage = (raw: string | null, respectUrlQuestion: boolean): boolean => {
      if (!raw) return false;
      try {
        const p = JSON.parse(raw) as Partial<PrismMemoryBlob>;
        if (p.v !== PRISM_MEMORY_VERSION || !Array.isArray(p.messages)) return false;
        setMessages(normalizePersistedMessages(p.messages));
        if (!(respectUrlQuestion && urlQuestionOnLoad) && typeof p.questionDraft === "string") {
          setQuestionDraft(p.questionDraft);
        }
        if (typeof p.feedbackNote === "string") setFeedbackNote(p.feedbackNote);
        if (typeof p.manualAccessTools === "boolean") setManualAccessTools(p.manualAccessTools);
        return true;
      } catch {
        return false;
      }
    };

    let bumpedHydration = false;
    if (prevWorkspaceKey.current === null) {
      prevWorkspaceKey.current = ws;
      hydrateFromStorage(localStorage.getItem(storeKey), true);
      bumpedHydration = true;
    } else if (prevWorkspaceKey.current !== ws) {
      prevWorkspaceKey.current = ws;
      setDrawer(null);
      if (!hydrateFromStorage(localStorage.getItem(storeKey), false)) {
        setMessages([]);
        setFeedbackNote("");
        setManualAccessTools(false);
        setQuestionDraft("");
      }
      bumpedHydration = true;
    }
    if (!bumpedHydration) return undefined;
    const t = window.setTimeout(() => setMemoryTick((n) => n + 1), 0);
    return () => window.clearTimeout(t);
  }, [tenant, ticker, searchParams]);

  /** Debounced persist of chat + draft + feedback for this tab session and workspace. */
  useEffect(() => {
    if (typeof window === "undefined") return;
    const sid = prismSessionId();
    const storeKey = prismMemoryStorageKey(sid, tenant, ticker);
    if (persistDebounceRef.current) clearTimeout(persistDebounceRef.current);
    persistDebounceRef.current = setTimeout(() => {
      persistDebounceRef.current = null;
      const blob: PrismMemoryBlob = {
        v: PRISM_MEMORY_VERSION,
        messages: messagesForStorage(messages),
        questionDraft,
        feedbackNote,
        manualAccessTools,
        updatedAt: Date.now(),
      };
      try {
        localStorage.setItem(storeKey, JSON.stringify(blob));
      } catch (e) {
        console.warn("Prism: could not persist workspace memory (quota?)", e);
      }
    }, 450);
    return () => {
      if (persistDebounceRef.current) {
        clearTimeout(persistDebounceRef.current);
        persistDebounceRef.current = null;
      }
    };
  }, [messages, questionDraft, feedbackNote, manualAccessTools, tenant, ticker, memoryTick]);

  const clearWorkspaceMemory = useCallback(() => {
    if (typeof window === "undefined") return;
    const sid = prismSessionId();
    localStorage.removeItem(prismMemoryStorageKey(sid, tenant, ticker));
    setMessages([]);
    setFeedbackNote("");
    setManualAccessTools(false);
    setQuestionDraft("");
  }, [tenant, ticker]);

  const tenantHeaders = useCallback(() => {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Prism-Tenant": tenant,
    };
    const p = principal.trim();
    if (p) h["X-Prism-Principal"] = p;
    return h;
  }, [tenant, principal]);

  const authFetchHeaders = useCallback(() => {
    const h: Record<string, string> = { "X-Prism-Tenant": tenant };
    const p = principal.trim();
    if (p) h["X-Prism-Principal"] = p;
    return h;
  }, [tenant, principal]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API}/v1/integrations?tenant=${encodeURIComponent(tenant)}`);
        if (r.ok && !cancelled) {
          setIntegrations((await r.json()) as IntegrationStatus);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenant]);

  const refreshCorpus = useCallback(async () => {
    const gen = ++corpusFetchGen.current;
    setCorpusLoading(true);
    setCorpusError(null);
    try {
      const r = await fetch(
        `${API}/v1/tenants/${encodeURIComponent(tenant)}/corpus?ticker=${encodeURIComponent(ticker)}`,
        { headers: authFetchHeaders(), cache: "no-store" },
      );
      const j = await responseJson<{ documents: CorpusDoc[] }>(r);
      if (gen !== corpusFetchGen.current) return;
      if (!j.ok) {
        setCorpusError(j.body.slice(0, 400));
        setCorpusDocs([]);
        return;
      }
      setCorpusDocs(j.data.documents ?? []);
    } catch (e) {
      if (gen !== corpusFetchGen.current) return;
      setCorpusError(String(e));
      setCorpusDocs([]);
    } finally {
      if (gen === corpusFetchGen.current) setCorpusLoading(false);
    }
  }, [API, tenant, ticker, authFetchHeaders]);

  useEffect(() => {
    void refreshCorpus();
  }, [refreshCorpus]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const ingest = useCallback(async () => {
    setBusy(true);
    try {
      const r = await fetch(`${API}/v1/ingest`, {
        method: "POST",
        headers: tenantHeaders(),
        body: JSON.stringify({
          tenant_id: tenant,
          ticker,
          transcript,
          filing_excerpt: filing,
          internal_notes: "Analyst note: guidance language sounds more cautious than headline beat.",
        }),
      });
      const ing = await responseJson<Record<string, unknown>>(r);
      if (!ing.ok) {
        setCorpusError(`Ingest failed: HTTP ${ing.status} — ${ing.body.slice(0, 400)}`);
      } else {
        await refreshCorpus();
      }
    } finally {
      setBusy(false);
    }
  }, [ticker, transcript, filing, tenant, tenantHeaders, refreshCorpus]);

  const sendFeedback = useCallback(
    async (thumbs: number, runId: string) => {
      setBusy(true);
      try {
        const r = await fetch(`${API}/v1/runs/${runId}/feedback`, {
          method: "POST",
          headers: tenantHeaders(),
          body: JSON.stringify({
            thumbs,
            note: feedbackNote.trim() || null,
          }),
        });
        if (!r.ok) {
          const t = await r.text();
          setCorpusError(`Feedback: HTTP ${r.status} ${t.slice(0, 200)}`);
        }
      } finally {
        setBusy(false);
      }
    },
    [API, feedbackNote, tenantHeaders],
  );

  const otherDemoWorkspaces = useMemo(
    () => DEMO_WORKSPACES.filter((w) => !(w.tenant === tenant && w.ticker === ticker)),
    [tenant, ticker],
  );

  const hasCrossClientHints = Boolean(CROSS_CLIENT_HINTS[tenant]?.length);

  const submitEvidenceRequest = useCallback(async () => {
    const [st, stk] = evidenceTargetKey.split("|");
    if (!st || !stk) {
      setEvidenceStatus("Choose a client workspace.");
      return;
    }
    setBusy(true);
    setEvidenceStatus(null);
    try {
      const r = await fetch(`${API}/v1/evidence-access-requests`, {
        method: "POST",
        headers: tenantHeaders(),
        body: JSON.stringify({
          chunk_id: null,
          subject_tenant_id: st,
          subject_ticker: stk,
          request_note:
            evidenceNote.trim() ||
            `Demo: request read access to ${st} / ${stk} corpus from current workspace ${tenant} (${ticker}).`,
        }),
      });
      const j = await responseJson<{ request_id: string }>(r);
      if (!j.ok) {
        setEvidenceStatus(j.body.slice(0, 500));
        return;
      }
      setEvidenceStatus(`Request recorded (id ${j.data.request_id}).`);
      setEvidenceModalOpen(false);
      setEvidenceNote("");
    } finally {
      setBusy(false);
    }
  }, [API, evidenceTargetKey, evidenceNote, tenant, ticker, tenantHeaders]);

  const runPipeline = useCallback(
    async (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) return;

      const userId = crypto.randomUUID();
      const asstId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        { id: userId, role: "user", content: trimmed },
        {
          id: asstId,
          role: "assistant",
          content: "",
          bundle: null,
          loading: true,
          phase: "Starting…",
        },
      ]);

      const patchAssistant = (patch: Partial<Extract<ChatMessage, { role: "assistant" }>>) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === asstId && m.role === "assistant" ? { ...m, ...patch } : m)),
        );
      };

      setBusy(true);
      try {
        const cr = await fetch(`${API}/v1/runs`, {
          method: "POST",
          headers: tenantHeaders(),
          body: JSON.stringify({ tenant_id: tenant, ticker, question: trimmed, include_mcp: true }),
        });
        const cj = await responseJson<{ run_id: string }>(cr);
        if (!cj.ok) {
          patchAssistant({
            loading: false,
            content: `Run failed to start (HTTP ${cj.status}): ${cj.body.slice(0, 600)}`,
            phase: undefined,
          });
          return;
        }
        const runId = cj.data.run_id;

        const fetchBundle = async (): Promise<Bundle | null> => {
          const gr = await fetch(`${API}/v1/runs/${runId}`, { headers: authFetchHeaders() });
          const bj = await responseJson<Bundle>(gr);
          if (!bj.ok) return null;
          return bj.data;
        };

        const waitForCompleted = async (maxMs: number): Promise<Bundle | null> => {
          const deadline = Date.now() + maxMs;
          while (Date.now() < deadline) {
            const b = await fetchBundle();
            if (!b) return null;
            if (b.run.status === "completed" && b.run.thesis_json != null) return b;
            if (b.run.status === "failed") return b;
            await new Promise((r) => setTimeout(r, 900));
          }
          return null;
        };

        const sseBundle: { current: Bundle | null } = { current: null };
        await new Promise<void>((resolve) => {
          let done = false;
          const sp = new URLSearchParams({ include_mcp: "true", tenant });
          const p = principal.trim();
          if (p) sp.set("principal", p);
          const es = new EventSource(`${API}/v1/runs/${runId}/stream?${sp.toString()}`);
          const finish = () => {
            if (done) return;
            done = true;
            try {
              es.close();
            } catch {
              /* ignore */
            }
            resolve();
          };
          es.onmessage = (ev) => {
            try {
              const raw = ev.data ?? "";
              if (raw.startsWith("<") || raw.includes("Internal Server")) return;
              const data = JSON.parse(raw) as {
                event: string;
                bundle?: Bundle;
                message?: string;
                phase?: string;
                model?: string;
                message_text?: string;
              };
              if (data.event === "phase") {
                const bits = [data.phase, data.message, data.model].filter(Boolean).join(" · ");
                patchAssistant({ phase: bits || "Working…" });
                return;
              }
              if (data.event === "hop") {
                const hop = data as { agent?: string; duration_ms?: number };
                patchAssistant({
                  phase: `${hop.agent ?? "hop"} · ${hop.duration_ms != null ? `${hop.duration_ms}ms` : ""}`,
                });
                return;
              }
              if (data.event === "error") {
                patchAssistant({ phase: data.message ?? "error", loading: false });
                finish();
                return;
              }
              if ((data.event === "cached" || data.event === "bundle") && data.bundle) {
                sseBundle.current = data.bundle;
                finish();
              }
            } catch {
              /* ignore */
            }
          };
          es.onerror = () => finish();
        });

        let latest: Bundle | null = sseBundle.current;
        if (!latest || latest.run.status !== "completed" || latest.run.thesis_json == null) {
          const polled = await waitForCompleted(240_000);
          if (polled) latest = polled;
        }

        let evalResult: Record<string, unknown> | null = null;
        if (latest?.run.status === "completed" && latest.run.thesis_json != null) {
          const er = await fetch(`${API}/v1/eval/regression`, {
            method: "POST",
            headers: tenantHeaders(),
            body: JSON.stringify({ run_id: runId }),
          });
          const evj = await responseJson<Record<string, unknown>>(er);
          if (evj.ok) evalResult = evj.data;
        }

        if (!latest) {
          patchAssistant({
            loading: false,
            content: "No result returned (timeout or error). Check API logs.",
            phase: undefined,
          });
          return;
        }

        const thesis = latest.run.thesis_json as Record<string, unknown> | undefined;
        const narrative = thesisNarrative(thesis);
        const stance = thesisStance(thesis);
        const head =
          stance && narrative
            ? `**${stance}** — ${narrative}`
            : narrative || "(No thesis narrative yet.)";

        patchAssistant({
          loading: false,
          content: head,
          bundle: latest,
          phase: undefined,
          evalResult,
          qualityPassed: latest.run.quality_passed ?? null,
          qualityReport: latest.run.quality_report ?? null,
        });
      } catch (e) {
        patchAssistant({
          loading: false,
          content: `Error: ${String(e)}`,
          phase: undefined,
        });
      } finally {
        setBusy(false);
      }
    },
    [ticker, tenant, principal, tenantHeaders, authFetchHeaders],
  );

  const onSend = useCallback(() => {
    const q = questionDraft.trim();
    if (!q || busy) return;
    setQuestionDraft("");
    void runPipeline(q);
  }, [questionDraft, busy, runPipeline]);

  const lastFeedbackAssistantId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "assistant" && !m.loading && m.bundle) return m.id;
    }
    return null;
  }, [messages]);

  const drawerBody = useMemo(() => {
    if (!drawer) return null;
    const { bundle, tab } = drawer;
    if (tab === "hops") {
      return (
        <ol className="space-y-3 text-sm">
          {bundle.hops.map((h) => {
            const pl = h.payload as Record<string, unknown>;
            const llmTxt = typeof pl.llm_response_text === "string" ? pl.llm_response_text : null;
            const { llm_response_text: _omitLlm, ...restPayload } = pl;
            return (
              <li key={h.id} className="rounded-lg border border-slate-800 bg-black/25 p-3">
                <div className="font-medium text-prism-accent">{h.agent}</div>
                <div className="mt-1 text-xs text-slate-500">
                  {h.intent ?? "—"} · {h.duration_ms ?? "?"}ms
                </div>
                {llmTxt ? (
                  <>
                    <div className="mt-3 text-[10px] font-semibold uppercase tracking-wide text-emerald-400/95">
                      LLM response (raw)
                    </div>
                    <pre className="mt-1 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded border border-emerald-900/45 bg-emerald-950/25 p-2.5 text-[11px] leading-relaxed text-emerald-50/95">
                      {llmTxt}
                    </pre>
                  </>
                ) : (
                  h.agent !== "Research" && (
                    <p className="mt-2 text-[10px] text-slate-600">No raw LLM text stored for this hop (older run).</p>
                  )
                )}
                <div className="mt-3 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  Hop payload (metadata)
                </div>
                <pre className="mt-1 max-h-48 overflow-auto rounded bg-black/40 p-2 text-[11px] text-slate-400">
                  {JSON.stringify(restPayload, null, 2)}
                </pre>
              </li>
            );
          })}
        </ol>
      );
    }
    if (tab === "matrix") {
      return (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400">
                <th className="py-2 pr-3">Theme</th>
                <th className="py-2 pr-3">Summary</th>
                <th className="py-2 pr-3">Conf.</th>
                <th className="py-2">Citations</th>
              </tr>
            </thead>
            <tbody>
              {bundle.matrix_rows.map((row, i) => (
                <tr key={i} className="border-b border-slate-800 align-top">
                  <td className="py-2 pr-3 font-medium text-prism-accent">{row.theme}</td>
                  <td className="py-2 pr-3 text-slate-300">{row.summary}</td>
                  <td className="py-2 pr-3">{row.confidence != null ? row.confidence.toFixed(2) : "—"}</td>
                  <td className="py-2 text-xs text-slate-500">{JSON.stringify(row.citation_ids)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    if (tab === "cross_reference") {
      const crossHints = CROSS_CLIENT_HINTS[tenant];
      if (!crossHints?.length) {
        return (
          <p className="text-xs leading-relaxed text-slate-500">
            Cross-reference demo is not configured for this workspace.
          </p>
        );
      }
      const ll = bundle.local_learning;
      const runSuggests = ll?.suggest_team_boundary_request === true;
      const showFullTools = manualAccessTools || runSuggests;
      return (
        <div className="space-y-4 text-sm">
          {!showFullTools && (
            <div className="rounded-lg border border-slate-800/90 bg-slate-950/40 p-3">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Local learning layer (this run)
              </div>
              <p className="mt-1 text-[10px] leading-snug text-slate-500">
                Evidence-access tooling stays compact until retrieval + quality signals for{" "}
                <span className="font-mono text-slate-400">this run</span> suggest material may sit with another team,
                or you use the override below.
              </p>
              {ll && (
                <p className="mt-2 text-[10px] leading-snug text-slate-500">
                  Score <span className="font-mono text-slate-400">{ll.confidence}</span>
                  {ll.signals?.length ? (
                    <>
                      {" "}
                      · <span className="text-slate-500">{ll.signals.join(", ")}</span>
                    </>
                  ) : null}
                  {ll.narrative ? (
                    <>
                      <br />
                      <span className="text-slate-600">{ll.narrative}</span>
                    </>
                  ) : null}
                </p>
              )}
              <button
                type="button"
                className="mt-2 w-full rounded border border-slate-700 bg-slate-900/80 px-2 py-2 text-[11px] text-slate-300 hover:bg-slate-800"
                onClick={() => setManualAccessTools(true)}
              >
                Show cross-reference tools anyway (demo override)
              </button>
            </div>
          )}
          {showFullTools && (
            <>
              <div className="rounded-lg border border-amber-900/40 bg-amber-950/20 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-amber-200/90">
                  {runSuggests ? "Local layer: possible other-team evidence" : "Demo: cross-tenant access (manual)"}
                </div>
                {runSuggests && ll && (
                  <p className="mt-1 text-[10px] leading-snug text-amber-100/80">
                    Signals: {ll.signals?.join(", ") || "—"} · confidence{" "}
                    <span className="font-mono">{ll.confidence}</span>
                    {ll.retrieval_summary?.vector_chunks != null ? (
                      <>
                        {" "}
                        · internal chunks{" "}
                        <span className="font-mono">{ll.retrieval_summary.vector_chunks}</span>
                      </>
                    ) : null}
                    . Formal access requests align with federated workflows (analyst feedback → local adapters; clip +
                    PII scrub before any shared update).
                  </p>
                )}
                {!runSuggests && (
                  <p className="mt-1 text-[10px] leading-snug text-slate-500">
                    Manual override: load a seeded cross-tenant question or open the modal to target another workspace.
                  </p>
                )}
                <p className="mt-1 text-[10px] leading-snug text-slate-500">
                  Questions below match <em>another</em> client&apos;s filings — thin retrieval here shows tenant
                  isolation vs. a governed access request.
                </p>
                <ul className="mt-2 space-y-2">
                  {crossHints.map((h, idx) => (
                    <li key={idx} className="rounded border border-slate-800/80 bg-black/15 p-2">
                      <p className="text-[11px] text-slate-400">{h.answerHint}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <button
                          type="button"
                          className="rounded bg-slate-800 px-2 py-1 text-[10px] text-slate-200 hover:bg-slate-700"
                          onClick={() => setQuestionDraft(h.question)}
                        >
                          Load question
                        </button>
                        <button
                          type="button"
                          className="rounded bg-amber-900/50 px-2 py-1 text-[10px] text-amber-100 hover:bg-amber-900/70"
                          onClick={() => {
                            setEvidenceTargetKey(`${h.subjectTenant}|${h.subjectTicker}`);
                            setEvidenceNote(
                              `Requesting access to ${h.subjectTenant} / ${h.subjectTicker} to answer: ${h.question}`,
                            );
                            setEvidenceModalOpen(true);
                          }}
                        >
                          Request info from that client…
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              {otherDemoWorkspaces.length > 0 && (
                <button
                  type="button"
                  className="w-full rounded-lg border border-teal-800/60 bg-teal-950/30 px-3 py-2 text-left text-[11px] font-medium text-teal-100 hover:bg-teal-950/50"
                  onClick={() => {
                    const first = otherDemoWorkspaces[0];
                    setEvidenceTargetKey(`${first.tenant}|${first.ticker}`);
                    setEvidenceNote("");
                    setEvidenceStatus(null);
                    setEvidenceModalOpen(true);
                  }}
                >
                  Request information from another client…
                </button>
              )}
            </>
          )}
        </div>
      );
    }
    return (
      <ul className="space-y-3 text-sm">
        {bundle.contradictions.map((c, i) => (
          <li key={i} className="rounded-lg border border-amber-900/50 bg-amber-950/25 p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-amber-200/90">
              {c.tension_type ?? "tension"}
            </div>
            <p className="mt-2 leading-relaxed text-slate-200">{c.description}</p>
          </li>
        ))}
      </ul>
    );
  }, [drawer, tenant, manualAccessTools, otherDemoWorkspaces]);

  return (
    <div className="prism-root flex h-dvh flex-col overflow-hidden bg-prism-bg text-slate-100">
      <header className="flex shrink-0 items-center justify-between border-b border-slate-800 bg-prism-panel/90 px-4 py-2 backdrop-blur">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-lg font-semibold tracking-tight text-prism-accent hover:underline">
            Prism
          </Link>
          {integrations && (
            <div className="hidden flex-wrap gap-1.5 text-[10px] sm:flex">
              <span className="rounded border border-slate-700 bg-slate-900/80 px-1.5 py-0.5 font-mono text-slate-400">
                {integrations.llm.model_id}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="hidden rounded border border-slate-700 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 sm:inline-block"
          >
            Demo personas
          </Link>
          <button
            type="button"
            onClick={() => setSettingsOpen((o) => !o)}
            className="rounded border border-slate-700 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
          >
            Workspace settings
          </button>
        </div>
      </header>

      {demoClientLabel && (
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-teal-900/40 bg-teal-950/35 px-4 py-2 text-xs text-teal-100/95">
          <p>
            <span className="font-semibold text-teal-200">{demoClientLabel}</span>
            <span className="text-teal-100/80"> — corpus & runs are isolated to </span>
            <span className="font-mono text-teal-200/90">{tenant}</span>
            <span className="text-teal-100/80"> + ticker </span>
            <span className="font-mono text-teal-200/90">{ticker}</span>
            <span className="text-teal-100/80"> (other personas do not see these documents).</span>
          </p>
          <Link href="/" className="shrink-0 font-medium text-teal-300 hover:underline">
            Switch client
          </Link>
        </div>
      )}

      {settingsOpen && (
        <div className="shrink-0 border-b border-slate-800 bg-slate-950/80 px-4 py-3">
          <div className="mx-auto flex max-w-3xl flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
            <label className="flex min-w-[140px] flex-1 flex-col gap-1 text-[10px] uppercase text-slate-500">
              Tenant
              <input
                className="rounded border border-slate-700 bg-prism-bg px-2 py-1.5 text-sm font-mono"
                value={tenant}
                onChange={(e) => setTenant(e.target.value.trim() || "default")}
              />
            </label>
            <label className="flex min-w-[180px] flex-1 flex-col gap-1 text-[10px] uppercase text-slate-500">
              Principal (RBAC)
              <input
                className="rounded border border-slate-700 bg-prism-bg px-2 py-1.5 text-sm font-mono"
                value={principal}
                onChange={(e) => setPrincipal(e.target.value)}
                placeholder="X-Prism-Principal"
              />
            </label>
            <p className="w-full text-[11px] text-slate-500">
              SSE uses the <code className="text-slate-400">principal</code> query param (EventSource cannot set
              headers). Match your API <code className="text-slate-400">PRISM_RBAC_STRICT</code> setup.
            </p>
            <div className="w-full rounded-lg border border-slate-800 bg-black/25 p-3">
              <p className="text-[11px] leading-relaxed text-slate-400">
                <strong className="text-slate-300">Session memory:</strong> this browser tab keeps chat, question
                draft, feedback note, and cross-reference override in <code className="text-slate-500">localStorage</code>{" "}
                keyed by tenant + ticker. Closing the tab clears the session id; opening a new tab starts a fresh
                memory namespace.
              </p>
              <button
                type="button"
                onClick={() => {
                  clearWorkspaceMemory();
                }}
                className="mt-2 rounded border border-rose-900/60 bg-rose-950/30 px-3 py-1.5 text-[11px] font-medium text-rose-200 hover:bg-rose-950/50"
              >
                Clear saved memory for this workspace
              </button>
            </div>
          </div>
        </div>
      )}

      {tenant === "default" && ticker === "DEMO" && !demoClientLabel && (
        <div className="prism-demo-hint">
          You are on the <strong>default</strong> workspace (no seeded corpus). For the three-client demo, open the{" "}
          <Link href="/">persona chooser</Link> — or set tenant/ticker to a seeded client (e.g.{" "}
          <code style={{ color: "#94a3b8" }}>frustrated_fran</code> /{" "}
          <code style={{ color: "#94a3b8" }}>FRANCLOUD</code>) after running{" "}
          <code style={{ color: "#94a3b8" }}>scripts/seed_demo_clients.py</code>.
        </div>
      )}

      <div className="prism-row flex min-h-0 flex-1">
        {/* Left: corpus + ingest */}
        <aside className="prism-sidebar flex w-[min(100%,280px)] shrink-0 flex-col border-r border-slate-800 bg-prism-panel/50">
          <div className="border-b border-slate-800 p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Company ticker
            </label>
            <input
              className="mt-1 w-full rounded border border-slate-700 bg-prism-bg px-2 py-2 text-sm font-semibold tracking-wide"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
            />
          </div>

          <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Corpus (retrieval)</h2>
            <button
              type="button"
              disabled={corpusLoading}
              onClick={() => void refreshCorpus()}
              className="text-[11px] text-teal-400 hover:underline disabled:opacity-40"
            >
              Refresh
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {corpusError && (
              <div className="mb-3 rounded border border-rose-900/60 bg-rose-950/30 p-2 text-[11px] text-rose-200">
                {corpusError}
              </div>
            )}
            {corpusLoading && <p className="text-xs text-slate-500">Loading documents…</p>}
            {!corpusLoading && corpusDocs.length === 0 && !corpusError && (
              <div className="space-y-2">
                <p className="text-xs leading-relaxed text-slate-500">
                  No ingested documents for this ticker. Expand <strong>Ingest</strong> below to add transcript +
                  filing text the agents will retrieve against.
                </p>
                {demoClientLabel && (
                  <div className="rounded-lg border border-amber-800/50 bg-amber-950/30 p-2.5 text-[11px] leading-snug text-amber-100/95">
                    <strong className="text-amber-200">Where did the demo files go?</strong> They are still in
                    Postgres if you seeded earlier, but rows may use the <em>old</em> tickers{" "}
                    <code className="rounded bg-black/30 px-1 font-mono text-amber-50/90">FRAN</code>,{" "}
                    <code className="rounded bg-black/30 px-1 font-mono text-amber-50/90">ANDY</code>,{" "}
                    <code className="rounded bg-black/30 px-1 font-mono text-amber-50/90">CARL</code> while this UI
                    now looks for{" "}
                    <code className="rounded bg-black/30 px-1 font-mono text-amber-50/90">FRANCLOUD</code> /{" "}
                    <code className="font-mono text-amber-50/90">MERIDIAN</code> /{" "}
                    <code className="font-mono text-amber-50/90">SABLE</code>.
                    <p className="mt-2 text-amber-100/85">
                      Fix: from repo root run{" "}
                      <code className="rounded bg-black/35 px-1 font-mono text-[10px] text-slate-200">
                        ./scripts/apply_migrations.sh
                      </code>{" "}
                      (includes <code className="font-mono text-[10px]">004_rename_demo_tickers_to_company.sql</code>)
                      <strong className="mx-1">or</strong> re-seed with{" "}
                      <code className="rounded bg-black/35 px-1 font-mono text-[10px] text-slate-200">
                        PYTHONPATH=apps/api/src:. python3.11 scripts/seed_demo_clients.py
                      </code>
                      , then press <strong>Refresh</strong> above.
                    </p>
                  </div>
                )}
              </div>
            )}
            <ul className="space-y-2">
              {integrations?.you_com.search_configured && (
                <li className="rounded-lg border border-teal-900/40 bg-teal-950/20 px-3 py-2">
                  <div className="text-xs font-medium text-teal-200">You.com live search</div>
                  <p className="mt-0.5 text-[10px] leading-snug text-slate-500">
                    Merged into the research hop with your corpus (when <code className="text-slate-400">YOU_API_KEY</code>{" "}
                    is set).
                  </p>
                </li>
              )}
              {corpusDocs.map((d) => (
                <li
                  key={d.id}
                  className="rounded-lg border border-slate-800 bg-black/20 px-3 py-2 transition hover:border-slate-600"
                >
                  <div className="line-clamp-2 text-sm font-medium text-slate-200">{d.title}</div>
                  <div className="mt-1 flex flex-wrap gap-x-2 text-[10px] text-slate-500">
                    <span className="rounded bg-slate-800/80 px-1.5 py-0.5 font-mono">{d.source_kind}</span>
                    <span>{d.chunk_count} chunks</span>
                  </div>
                </li>
              ))}
            </ul>

          </div>

          <div className="border-t border-slate-800">
            <button
              type="button"
              onClick={() => setIngestOpen((o) => !o)}
              className="flex w-full items-center justify-between px-3 py-2.5 text-left text-xs font-medium text-slate-300 hover:bg-slate-900/50"
            >
              <span>Ingest text corpus</span>
              <span className="text-slate-500">{ingestOpen ? "▾" : "▸"}</span>
            </button>
            {ingestOpen && (
              <div className="space-y-2 border-t border-slate-800/80 p-3">
                <label className="block text-[10px] uppercase text-slate-500">Transcript</label>
                <textarea
                  className="mb-2 max-h-28 min-h-[72px] w-full rounded border border-slate-700 bg-prism-bg px-2 py-1.5 text-xs"
                  value={transcript}
                  onChange={(e) => setTranscript(e.target.value)}
                />
                <label className="block text-[10px] uppercase text-slate-500">Filing excerpt</label>
                <textarea
                  className="mb-2 max-h-28 min-h-[72px] w-full rounded border border-slate-700 bg-prism-bg px-2 py-1.5 text-xs"
                  value={filing}
                  onChange={(e) => setFiling(e.target.value)}
                />
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void ingest()}
                  className="w-full rounded bg-slate-700 py-2 text-xs font-medium hover:bg-slate-600 disabled:opacity-40"
                >
                  Ingest into index
                </button>
              </div>
            )}
          </div>
        </aside>

        {/* Center: chat */}
        <main className="prism-main flex min-w-0 min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            {messages.length === 0 && (
              <div className="mx-auto mt-8 max-w-xl rounded-2xl border border-slate-800 bg-prism-panel/60 p-6 text-center">
                <p className="text-sm text-slate-300">
                  Ask a question about <span className="font-mono text-prism-accent">{ticker}</span>. Prism will
                  retrieve from the documents on the left (plus You.com when configured), then run analysis and
                  thesis agents.
                </p>
              </div>
            )}
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {messages.map((m) => {
                if (m.role === "user") {
                  return (
                    <div key={m.id} className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-teal-900/40 px-4 py-3 text-sm leading-relaxed text-teal-50 ring-1 ring-teal-800/50">
                        {m.content}
                      </div>
                    </div>
                  );
                }
                const stanceMatch = /^\*\*([^*]+)\*\*\s*—\s*/.exec(m.content);
                const rest = stanceMatch ? m.content.slice(stanceMatch[0].length) : m.content;
                return (
                  <div key={m.id} className="flex justify-start">
                    <div className="max-w-[92%] rounded-2xl rounded-bl-md border border-slate-800 bg-prism-panel px-4 py-3 shadow-lg">
                      {m.loading ? (
                        <div className="flex items-center gap-3 text-sm text-slate-400">
                          <span
                            className="inline-block h-4 w-4 animate-pulse rounded-full bg-prism-accent/60"
                            aria-hidden
                          />
                          <span>{m.phase ?? "Running pipeline…"}</span>
                        </div>
                      ) : (
                        <>
                          {stanceMatch && (
                            <div className="mb-2 inline-flex rounded-full border border-slate-600 bg-slate-900/80 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-prism-accent">
                              {stanceMatch[1]}
                            </div>
                          )}
                          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{rest}</p>
                          {m.qualityReport != null && (
                            <div
                              className={`mt-3 rounded-lg border px-2 py-1.5 text-[11px] ${
                                m.qualityPassed
                                  ? "border-emerald-800/60 bg-emerald-950/30 text-emerald-200"
                                  : "border-amber-800/60 bg-amber-950/30 text-amber-100"
                              }`}
                            >
                              Quality gate: {m.qualityPassed ? "passed" : "review"}{" "}
                              <span className="font-mono opacity-80">{JSON.stringify(m.qualityReport)}</span>
                            </div>
                          )}
                          {m.evalResult && (
                            <div className="mt-2 rounded border border-slate-700 bg-black/20 p-2 text-[11px] text-slate-400">
                              Regression eval: passed {String(m.evalResult.passed)} / failed{" "}
                              {String(m.evalResult.failed)}
                            </div>
                          )}
                          {m.bundle && (
                            <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-800 pt-3">
                              <button
                                type="button"
                                onClick={() => setDrawer({ bundle: m.bundle as Bundle, tab: "hops" })}
                                className="rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
                              >
                                View hops
                              </button>
                              <button
                                type="button"
                                onClick={() => setDrawer({ bundle: m.bundle as Bundle, tab: "matrix" })}
                                className="rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
                              >
                                View matrix
                              </button>
                              <button
                                type="button"
                                onClick={() => setDrawer({ bundle: m.bundle as Bundle, tab: "contradictions" })}
                                className="rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
                              >
                                Contradictions
                              </button>
                              {hasCrossClientHints && (
                                <button
                                  type="button"
                                  onClick={() => setDrawer({ bundle: m.bundle as Bundle, tab: "cross_reference" })}
                                  className="rounded-lg border border-amber-800/60 bg-amber-950/35 px-3 py-1.5 text-xs font-medium text-amber-100 hover:bg-amber-950/55"
                                >
                                  Cross reference
                                </button>
                              )}
                            </div>
                          )}
                          {m.bundle?.run.id && !m.loading && m.id === lastFeedbackAssistantId && (
                            <div className="mt-3 space-y-2">
                              <textarea
                                className="w-full rounded border border-slate-700 bg-prism-bg px-2 py-1.5 text-[11px]"
                                placeholder="Optional feedback note (PII scrubbed server-side)"
                                value={feedbackNote}
                                onChange={(e) => setFeedbackNote(e.target.value)}
                                rows={2}
                              />
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={() => {
                                    const rid = m.bundle?.run.id;
                                    if (rid) void sendFeedback(1, rid);
                                  }}
                                  className="inline-flex items-center justify-center rounded bg-slate-700 px-3 py-2 text-slate-100 hover:bg-slate-600 disabled:opacity-40"
                                  aria-label="Thumbs up"
                                  title="Thumbs up"
                                >
                                  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                                    <path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z" />
                                  </svg>
                                </button>
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={() => {
                                    const rid = m.bundle?.run.id;
                                    if (rid) void sendFeedback(-1, rid);
                                  }}
                                  className="inline-flex items-center justify-center rounded bg-slate-700 px-3 py-2 text-slate-100 hover:bg-slate-600 disabled:opacity-40"
                                  aria-label="Thumbs down"
                                  title="Thumbs down"
                                >
                                  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                                    <path d="M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z" />
                                  </svg>
                                </button>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
              <div ref={chatEndRef} />
            </div>
          </div>

          <div className="shrink-0 border-t border-slate-800 bg-prism-panel/90 p-3 backdrop-blur">
            <div className="mx-auto flex max-w-3xl gap-2">
              <textarea
                className="min-h-[52px] flex-1 resize-none rounded-xl border border-slate-700 bg-prism-bg px-3 py-2 text-sm leading-snug text-slate-100 placeholder:text-slate-600 focus:border-teal-700 focus:outline-none focus:ring-1 focus:ring-teal-700/40"
                placeholder={`Ask about ${ticker}…`}
                value={questionDraft}
                onChange={(e) => setQuestionDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onSend();
                  }
                }}
                rows={2}
              />
              <button
                type="button"
                disabled={busy || !questionDraft.trim()}
                onClick={onSend}
                className="self-end rounded-xl bg-teal-600 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-teal-500 disabled:opacity-40"
              >
                Send
              </button>
            </div>
            {integrations?.llm.model_config_warning && (
              <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-amber-200/90">
                {integrations.llm.model_config_warning}
              </p>
            )}
          </div>
        </main>
      </div>

      {/* Drawer */}
      {drawer && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/55 backdrop-blur-[2px]"
          role="presentation"
          onClick={() => setDrawer(null)}
        >
          <div
            className="flex h-full w-full max-w-lg flex-col border-l border-slate-800 bg-prism-panel shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label="Run details"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
              <span className="text-sm font-semibold text-slate-200">Run details</span>
              <button
                type="button"
                onClick={() => setDrawer(null)}
                className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="flex flex-wrap gap-1 border-b border-slate-800 px-2 py-2">
              {(["hops", "matrix", "contradictions"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setDrawer((d) => (d ? { ...d, tab: tab as DrawerTab } : null))}
                  className={`min-w-[4.5rem] flex-1 rounded-lg py-2 text-xs font-medium capitalize ${
                    drawer.tab === tab
                      ? "bg-teal-900/50 text-teal-100 ring-1 ring-teal-700/50"
                      : "text-slate-400 hover:bg-slate-800/80"
                  }`}
                >
                  {tab === "contradictions" ? "Contradictions" : tab}
                </button>
              ))}
              {hasCrossClientHints && (
                <button
                  type="button"
                  onClick={() => setDrawer((d) => (d ? { ...d, tab: "cross_reference" } : null))}
                  className={`min-w-[5.5rem] flex-1 rounded-lg py-2 text-xs font-medium ${
                    drawer.tab === "cross_reference"
                      ? "bg-amber-900/45 text-amber-100 ring-1 ring-amber-700/50"
                      : "text-slate-400 hover:bg-slate-800/80"
                  }`}
                >
                  Cross reference
                </button>
              )}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">{drawerBody}</div>
          </div>
        </div>
      )}

      {evidenceModalOpen && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4"
          role="presentation"
          onClick={() => setEvidenceModalOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-slate-700 bg-prism-panel p-4 shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label="Request information"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-sm font-semibold text-slate-100">Request information from…</h2>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
              Records a governance request from your current workspace (
              <span className="font-mono text-slate-400">{tenant}</span> /{" "}
              <span className="font-mono text-slate-400">{ticker}</span>) to read another client&apos;s ingested
              corpus. Demo only — requires <span className="font-mono">X-Prism-Principal</span>.
            </p>
            <label className="mt-3 block text-[10px] uppercase text-slate-500">Target client</label>
            <select
              className="mt-1 w-full rounded border border-slate-700 bg-prism-bg px-2 py-2 text-sm text-slate-100"
              value={evidenceTargetKey}
              onChange={(e) => setEvidenceTargetKey(e.target.value)}
            >
              {otherDemoWorkspaces.map((w) => (
                <option key={`${w.tenant}|${w.ticker}`} value={`${w.tenant}|${w.ticker}`}>
                  {w.label} ({w.tenant} · {w.ticker})
                </option>
              ))}
            </select>
            <label className="mt-3 block text-[10px] uppercase text-slate-500">Note (optional)</label>
            <textarea
              className="mt-1 min-h-[72px] w-full rounded border border-slate-700 bg-prism-bg px-2 py-1.5 text-xs text-slate-100"
              value={evidenceNote}
              onChange={(e) => setEvidenceNote(e.target.value)}
              placeholder="What evidence do you need and why?"
            />
            {evidenceStatus && <p className="mt-2 text-[11px] text-amber-200/90">{evidenceStatus}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
                onClick={() => {
                  setEvidenceModalOpen(false);
                  setEvidenceStatus(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy || !principal.trim()}
                className="rounded bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-500 disabled:opacity-40"
                onClick={() => void submitEvidenceRequest()}
              >
                Submit request
              </button>
            </div>
            {!principal.trim() && (
              <p className="mt-2 text-[10px] text-rose-300/90">Set Principal (e.g. demo@prism.local) in settings first.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
