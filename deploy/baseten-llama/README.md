# Deploy Llama on Baseten (config-only)

This folder matches Baseten’s **“build your first model”** flow: one `config.yaml`, Hugging Face weights, TensorRT-LLM build, **OpenAI-compatible** endpoint. See the official guide: [Build your first model](https://docs.baseten.co/development/model/build-your-first-model).

## 1. Prerequisites

- [Baseten account](https://app.baseten.co/signup) and [API key](https://app.baseten.co/settings/account/api_keys)
- [Truss CLI](https://docs.baseten.co/development/model/overview) (`pip install truss` or `uv pip install truss`)
- For **gated** Meta Llama repos: accept the license on Hugging Face, then `export HF_TOKEN=...` before pushing

## 2. Log in

```bash
export BASETEN_API_KEY="your-key"
truss login
# or rely on BASETEN_API_KEY only (see Baseten docs)
```

## 3. Deploy

From **this directory** (`prism/deploy/baseten-llama/`):

```bash
truss push
```

Wait until the deployment is **Active** in the [Baseten dashboard](https://app.baseten.co/models/). Note:

- **Model ID** — from the URL `/models/<model_id>/` or the `truss push` output.
- **`model_name`** in `config.yaml` — must match the `model=` string you send to the OpenAI API (here: `Llama-3.2-3B-Instruct` by default).

## 4. Call your deployment (OpenAI-compatible)

Baseten gives a **per-model** base URL like:

`https://model-<MODEL_ID>.api.baseten.co/environments/production/sync/v1`

Example (from [Baseten docs](https://docs.baseten.co/development/model/build-your-first-model)):

```bash
curl -s "https://model-<MODEL_ID>.api.baseten.co/environments/production/sync/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Api-Key $BASETEN_API_KEY" \
  -d '{
    "model": "Llama-3.2-3B-Instruct",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

If you change `model_name` / HF `repo` in `config.yaml`, use the same string for `"model"` in requests.

## 5. Wire Prism to this deployment

Prism uses LiteLLM with an OpenAI-compatible base URL.

**Self-deployed Engine (this Truss project):**

```bash
BASETEN_API_KEY=...
# Use your deployment-specific base URL (must end with /v1 per OpenAI convention):
BASETEN_OPENAI_BASE=https://model-<MODEL_ID>.api.baseten.co/environments/production/sync/v1
PRISM_ADK_MODEL=openai/Llama-3.2-3B-Instruct
```

Unset `PRISM_OPENAI_BASE` when using Baseten so routing stays on Baseten.

**Optional: Baseten Model APIs (no `truss push`)**

If you enable a managed Llama (or other) model from the [Model APIs](https://docs.baseten.co/inference/model-apis/overview) catalog, use the shared endpoint:

```bash
BASETEN_API_KEY=...
BASETEN_OPENAI_BASE=https://inference.baseten.co/v1
PRISM_ADK_MODEL=openai/<exact-slug-from-Baseten>
```

List slugs: `curl https://inference.baseten.co/v1/models -H "Authorization: Api-Key $BASETEN_API_KEY"`.

Then restart the Prism API (`uvicorn`).
