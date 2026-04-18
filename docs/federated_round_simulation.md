# Simulated federated learning round (server aggregation)

This note walks through **one training round** of **sample-weighted FedAvg** on a toy **2-D adapter vector**, aligned with how Prism’s optional Flower stretch (`apps/fl_stretch`) frames federation: **small tensors in, global adapter out** — not raw documents.

## Roles

| Role | In this simulation |
|------|---------------------|
| **Server** | Holds global adapter `w⁰`, broadcasts it to clients, receives client updates, runs **aggregation**. |
| **Client A** | Private local target vector (tenant-specific “ideal” adapter). Runs **one local fit** starting from `w⁰`. |
| **Client B** | Same, with a different private target. |

## One round, step by step

1. **Initialize** — Global adapter `w⁰ = [0, 0]` (float64 for stable arithmetic in the script).
2. **Broadcast** — Server sends `w⁰` to all participating clients (Flower does this implicitly each round).
3. **Local fit (on each client)** — Each client moves halfway toward its **private** target and adds tiny Gaussian noise (simulating stochastic mini-batch noise):

   `w' = w⁰ + α · (t − w⁰) + ε`, with `α = 0.5`, `ε ~ N(0, σ²I)`, `σ = 0.02`.

   Targets: **Tenant A** `t_A = [1.0, 0.2]`, **Tenant B** `t_B = [0.5, 0.9]` (same construction as `fl_prism.sim_toy`’s two “banks”).
4. **Upload** — Clients send only **`w'`** and a **sample-count proxy** `n_i` (here `n_A = 100`, `n_B = 150`) — not raw filings or transcripts.
5. **Server aggregation (FedAvg)** —

   `w¹ = (n_A · w'_A + n_B · w'_B) / (n_A + n_B)`.

   If every client used the same `n_i`, this reduces to a plain mean of the `w'` vectors.

## Reproduce the numbers

From the `prism` directory:

```bash
python3 scripts/simulate_federated_round.py
```

Optional: `--seed`, `--noise-scale`, `--local-lr`, `--n-a`, `--n-b`.

## Output for default hyperparameters (`seed=42`)

The script prints JSON; the important scalars are summarized here.

| Quantity | Value |
|----------|--------|
| `w⁰` | `[0.0, 0.0]` |
| `t_A` | `[1.0, 0.2]` |
| `t_B` | `[0.5, 0.9]` |
| `α` (local_lr) | `0.5` |
| `σ` (noise_scale) | `0.02` |
| `n_A`, `n_B` | `100`, `150` |
| `w'_A` | `[0.5099342830602247, 0.0972347139765763]` |
| `w'_B` | `[0.26295377076201387, 0.4804605971281605]` |
| **FedAvg** `w¹` (sample-weighted) | `[0.3617459756812982, 0.32717024386752686]` |
| FedAvg with equal client weights `(w'_A + w'_B)/2` | `[0.3864440269111193, 0.2888476555523684]` |

The weighted aggregate is pulled slightly toward **Tenant B**’s update because `n_B > n_A`.

## Relation to Prism’s Flower toy

- **`apps/fl_stretch/src/fl_prism/sim_toy.py`** runs **Flower’s** `start_simulation` with **FedAvg** and **one round**, using the same 2-D targets and a similar local update rule.
- **`scripts/simulate_federated_round.py`** is **numpy-only** so you can inspect one round **without** installing `flwr` / Ray — useful for decks and teaching.

## Production-shaped deltas (not implemented in the toy)

- **Secure aggregation** — Server learns `w¹` without observing each `w'_i` in the clear (e.g. masked sums).
- **DP on the aggregate** — Calibrated noise on `w¹` for a formal privacy guarantee.
- **Scope** — Federate **adapter deltas or LoRA weights** only; keep **tenant corpus** in the retrieval plane (see main Prism RAG path), orthogonal to this aggregation story.
