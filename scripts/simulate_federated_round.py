#!/usr/bin/env python3
"""Deterministic one-round FedAvg simulation (numpy only; no Flower/Ray).

Mirrors the *idea* of `apps/fl_stretch/src/fl_prism/sim_toy.py`: two tenants each
hold a private 2-D "adapter" target; the server starts from a global adapter,
clients take one local step toward their target plus small Gaussian noise, then
the server aggregates client weights (FedAvg).

Run from repo root:
  python3 scripts/simulate_federated_round.py
  python3 scripts/simulate_federated_round.py --seed 7
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np


def fedavg_aggregate(
    weights: list[np.ndarray],
    sample_counts: list[int],
) -> np.ndarray:
    total = float(sum(sample_counts))
    acc = np.zeros_like(weights[0], dtype=np.float64)
    for w, n in zip(weights, sample_counts, strict=True):
        acc += (float(n) / total) * w.astype(np.float64)
    return acc


def simulate_one_round(
    *,
    seed: int,
    noise_scale: float,
    local_lr: float,
    n_a: int,
    n_b: int,
) -> dict[str, Any]:
    # Legacy RandomState matches `np.random.seed` + sequential `randn` in `sim_toy.py`.
    rng = np.random.RandomState(seed)
    w0 = np.zeros(2, dtype=np.float64)
    target_a = np.array([1.0, 0.2], dtype=np.float64)
    target_b = np.array([0.5, 0.9], dtype=np.float64)

    def local_fit(target: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        noise = rng.randn(*w.shape).astype(np.float64) * noise_scale
        w_prime = w + (target - w) * local_lr + noise
        return w_prime.astype(np.float64), noise

    w_a, noise_a = local_fit(target_a, w0)
    w_b, noise_b = local_fit(target_b, w0)

    w_equal = fedavg_aggregate([w_a, w_b], [1, 1])
    w_weighted = fedavg_aggregate([w_a, w_b], [n_a, n_b])

    return {
        "seed": seed,
        "initial_global_adapter_w0": w0.tolist(),
        "private_local_targets": {
            "tenant_a": target_a.tolist(),
            "tenant_b": target_b.tolist(),
        },
        "hyperparameters": {
            "local_lr": local_lr,
            "noise_scale": noise_scale,
            "sample_counts": {"tenant_a": n_a, "tenant_b": n_b},
        },
        "client_updates_after_fit": {
            "tenant_a": {"w_prime": w_a.tolist(), "noise_draw": noise_a.tolist()},
            "tenant_b": {"w_prime": w_b.tolist(), "noise_draw": noise_b.tolist()},
        },
        "server_aggregation": {
            "method": "FedAvg",
            "formula_equal_n": "(w_a_prime + w_b_prime) / 2",
            "formula_weighted": "(n_a * w_a_prime + n_b * w_b_prime) / (n_a + n_b)",
            "aggregated_w_equal_client_weights": w_equal.tolist(),
            "aggregated_w_sample_weighted": w_weighted.tolist(),
        },
        "privacy_note": (
            "Only low-dimensional adapter tensors leave the client in this toy; "
            "raw corpus documents never enter the aggregation step."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Simulate one FedAvg server round (numpy).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--noise-scale", type=float, default=0.02)
    p.add_argument("--local-lr", type=float, default=0.5)
    p.add_argument("--n-a", type=int, default=100, help="Training sample count proxy for tenant A")
    p.add_argument("--n-b", type=int, default=150, help="Training sample count proxy for tenant B")
    args = p.parse_args()

    out = simulate_one_round(
        seed=args.seed,
        noise_scale=args.noise_scale,
        local_lr=args.local_lr,
        n_a=args.n_a,
        n_b=args.n_b,
    )
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
