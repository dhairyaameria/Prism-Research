# Prism

**Repository:** [github.com/dhairyaameria/Prism-Research](https://github.com/dhairyaameria/Prism-Research)

Multi-agent investment research copilot: **tenant-scoped RAG** (Postgres + **pgvector**), then **Analysis → Thesis** LLM stages on the default **fast** pipeline — or the full **Google ADK** chain. Served by **FastAPI**, **MCP** (`prism-market-intel`), optional **You.com** live search, **Baseten** / Ollama / OpenAI-compatible routing, **Veris**-style regression eval and packaging hooks, and a **Flower** federated-learning stretch (`apps/fl_stretch`). The **Next.js** demo landing walks through features, architecture, client isolation, server-side FL narrative, and applicability.

## Prerequisites

- Docker (for Postgres + pgvector)
- [uv](https://docs.astral.sh/uv/) (Python 3.11+)
- Node 20+ (for Next.js)
- **Baseten (default in `.env.example`):** `PRISM_LLM_PROVIDER=baseten`, **`BASETEN_API_KEY`**, and **`PRISM_ADK_MODEL=openai/<slug>`** from the [Model APIs](https://docs.baseten.co/inference/model-apis/overview) catalog — or use **Gemini** / **Ollama** / **vLLM** by omitting `PRISM_LLM_PROVIDER` and configuring keys as in the sections below
- Optional: [You.com](https://you.com/platform) API key for live search in MCP tools
- Optional: [Veris](https://veris.ai/) CLI + account for full simulation (`veris env push`, scenarios)

## Sponsor integrations

### Baseten (production inference)

Set **`PRISM_LLM_PROVIDER=baseten`** so every run uses **only** Baseten. Then configure (see [Baseten OpenAI compatibility](https://docs.baseten.co/inference/model-apis/overview)):

- `BASETEN_API_KEY` — mapped to `OPENAI_API_KEY` for LiteLLM
- `BASETEN_OPENAI_BASE` — default `https://inference.baseten.co/v1` (or your per-model deployment URL)
- `PRISM_ADK_MODEL` — must be `openai/<slug>` (list slugs: `curl -s https://inference.baseten.co/v1/models -H "Authorization: Api-Key $BASETEN_API_KEY"`)

`GET /v1/integrations` includes **`llm.baseten_only`** when this mode is active.

**Llama 4 Maverick (Baseten model library):** follow [Llama 4 Maverick](https://www.baseten.co/library/llama-4-maverick/) — copy **`model_url`** → `BASETEN_OPENAI_BASE` and the chat **`model`** string → `PRISM_ADK_MODEL=openai/<model>` from the model’s **API pane** (see comments in `.env.example`).

Requires `google-adk[extensions]` (already in `apps/api` deps) for LiteLLM-backed models.

### Open-source / local models (why Gemini at all?)

The stack is **Google ADK**; its built-in default is **Gemini** so the hackathon demo works with one API key and no GPU. The same `LlmAgent` pipeline supports **LiteLLM** model strings (`provider/model`), so you can run **open-weights** models locally or on your own GPU:

**Ollama** — install [Ollama](https://ollama.com/), run `ollama pull llama3.1` (or any tag), then in `.env`:

```bash
PRISM_ADK_MODEL=ollama/llama3.1
# optional if not localhost:11434
# PRISM_OLLAMA_BASE=http://127.0.0.1:11434
```

Keep the **Ollama app** (or `ollama serve`) running so something is listening on `127.0.0.1:11434`, or set **`PRISM_OLLAMA_BASE`** to wherever the daemon runs. The web UI calls **`GET /v1/integrations`** and shows **Ollama reachable** when `/api/tags` responds.

**vLLM / llama.cpp server / any OpenAI-compatible `/v1/chat/completions` host:**

```bash
PRISM_ADK_MODEL=openai/<exact-model-id-your-server-exposes>
PRISM_OPENAI_BASE=http://127.0.0.1:8000/v1
# PRISM_OPENAI_API_KEY=not-needed   # optional; many local servers ignore this
```

If both `BASETEN_API_KEY` and `PRISM_OPENAI_BASE` are set with `PRISM_ADK_MODEL=openai/...`, **Baseten wins** (same prefix). Use one or the other.

### You.com (enterprise search)

When **`YOU_API_KEY`** is set, MCP tool **`get_news_digest`** calls You.com **YDC Search** (`https://ydc-index.io/v1/search`, header `X-API-Key`). Otherwise it returns a structured mock.

Smoke test from the API: `GET /v1/you/preview?q=...` (requires the same key).

### Veris AI (simulation & CI gates)

1. **SDK (optional):** with `ENABLE_VERIS_MCP=1`, the API mounts Veris **FastAPI MCP** so you can package the same HTTP surface for Veris (`veris-ai` dependency). See [Veris Python SDK](https://pypi.org/project/veris-ai/).
2. **Sandbox contract:** `POST /v1/veris/chat` with `{ "message": "..." }` returns `{ "response": "<thesis narrative>", "run_id": "..." }`. Put `TICKER: AAPL` in the message to override the default (`VERIS_DEFAULT_TICKER`).
3. **CLI workflow** ([quickstart](https://docs.veris.ai/quickstart)): from the `prism/` repo root, install the Veris CLI and authenticate. You must **register the environment once** so Veris writes **`.veris/config.yaml`** (your remote `environment_id` for target **`prism`**). Without that file, `veris env push` and `veris scenarios create` print *“No environment configured for target 'prism'”*.

   ```bash
   pip install veris-cli          # or: uv tool install veris-cli
   cd prism
   veris login                    # browser; or: veris login YOUR_VERIS_API_KEY
   veris env create --name prism --agent-name Prism   # REQUIRED once per profile: creates env + .veris/config.yaml
   veris env push                 # build & deploy using .veris/Dockerfile.sandbox
   veris scenarios create         # generate scenarios (needs env id above)
   veris run                      # pick scenarios → simulations → report
   ```

   The **`--name prism`** flag must match the target key in [`.veris/veris.yaml`](.veris/veris.yaml) (`prism:`). This repo already ships **`.veris/veris.yaml`** (actor → **`POST /v1/veris/chat`** on port **8008**) and **`.veris/Dockerfile.sandbox`**; `env create` will not duplicate that block if `prism` is already defined.

   Push secrets for the sandbox LLM/DB as needed, for example: **`veris env vars set GOOGLE_API_KEY=... --secret`** (or your Ollama/OpenAI vars). See **`veris env vars --help`**.

## Setup

```bash
cd prism
cp .env.example .env
# edit .env — set GOOGLE_API_KEY and PRISM_REPO_ROOT to this repo's absolute path

docker compose up --build -d   # builds `Dockerfile.db` (init SQL baked in; avoids bind-mount issues on some Docker setups)

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e "./packages/adk_prism" -e "./mcp/prism-market-intel" -e "./apps/api" -e "./apps/fl_stretch"

cd apps/web && npm install && cd ../..
```

If you change `scripts/init.sql`, reset the volume so Postgres re-runs init scripts: `docker compose down -v && docker compose up --build -d`.

## Run API

```bash
cd prism
source .venv/bin/activate  # if not already active
export PRISM_REPO_ROOT="$(pwd)"
uvicorn prism_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Run Web UI

```bash
cd prism/apps/web
npm run dev
```

Open `http://localhost:3000`.

- **Workspace** — ingest sample transcript / filing / notes, then **Run agents** (chat + run drawer: hops, matrix, tensions, cross-reference, feedback).
- **Demo landing** (same origin, marketing tabs): **Prism Features** (product narrative), **Architecture Design** (layer diagram), **Client Simulation** (three seeded tenants → workspace links), **Server Analysis** (federated coordinator narrative + per-tenant **dummy round logs** in the shape of `fl-aggregates/round-1.txt`), **Applicability** (user personas, adjacent products such as Hebbia / AlphaSense, cross-industry agent + privacy use cases).

## Federated learning (toy, docs, sample aggregate)

- **Flower simulation** — pulls **Ray** via `flwr[simulation]` (`apps/fl_stretch`). Run from repo root:

  ```bash
  cd prism
  PYTHONPATH=apps/fl_stretch/src .venv/bin/python -m fl_prism.sim_toy
  ```

  Isolated from the ADK inference plane (no training inside the agent API process).

- **Deterministic one-round FedAvg (no Flower)** — reproduces the same *kind* of JSON as a real aggregate log:

  ```bash
  python3 scripts/simulate_federated_round.py
  ```

- **Write-up** — [`docs/federated_round_simulation.md`](docs/federated_round_simulation.md) walks through one server round (FedAvg, sample weights, privacy note).

- **Sample on disk** — [`fl-aggregates/round-1.txt`](fl-aggregates/round-1.txt) is a saved JSON snapshot for slides or tests.

## API quick reference

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/ingest` | Upload transcript / filing text for a ticker (`X-Prism-Tenant` or body `tenant_id`) |
| POST | `/v1/runs` | Create a run (`ticker`, `question`; tenant as header/body) |
| GET | `/v1/runs/{id}/stream` | SSE: ADK events + final `bundle` (`X-Prism-Tenant` or `?tenant=`) |
| GET | `/v1/runs/{id}` | JSON snapshot (tenant must match run) |
| POST | `/v1/eval/regression` | Static regression checks on a completed run |
| PUT | `/v1/tenants/{id}/llm-profile` | Per-tenant open model routing (`model_id`, bases, `*_env` key names only) |
| GET | `/v1/tenants/{id}/llm-profile` | Read tenant LLM config (no secret values) |
| GET | `/v1/integrations` | Per-tenant LLM/env status (`?tenant=`; no secrets) |
| GET | `/v1/you/preview` | You.com search smoke test (`q=` query param) |
| POST | `/v1/veris/chat` | Veris actor channel → full Prism run → thesis text |

## Sponsor pitch (one-liner)

Prism turns earnings calls and filings into a **cited, contradiction-aware matrix**, with **auditable hops**, **tenant-isolated retrieval**, **You.com-backed** context when configured, **Baseten** (or local) inference, hooks for **Veris** simulation and regression gates, and a **Flower**-style path for **adapter-only** federation without pooling raw client documents.
