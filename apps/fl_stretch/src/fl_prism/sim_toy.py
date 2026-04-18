"""
Toy Flower FedAvg on 2D numpy "adapter" vectors — simulates two bank tenants.

Run: `.venv/bin/python -m fl_prism.sim_toy` from the `prism` directory (PYTHONPATH includes `apps/fl_stretch/src`).
"""

from __future__ import annotations

import json
from typing import Any

import flwr as fl
import numpy as np
from flwr.common import ndarrays_to_parameters
from flwr.common.context import Context
from flwr.server.strategy import FedAvg


def _client(vec: np.ndarray, noise: float) -> fl.client.NumPyClient:
    class ToyClient(fl.client.NumPyClient):
        def get_parameters(self, config: dict[str, Any]) -> list[np.ndarray]:
            return [vec.copy()]

        def fit(
            self,
            parameters: list[np.ndarray],
            config: dict[str, Any],
        ) -> tuple[list[np.ndarray], int, dict[str, Any]]:
            base = parameters[0]
            updated = base + (vec - base) * 0.5 + np.random.randn(*base.shape).astype(np.float32) * noise
            return [updated.astype(np.float32)], 1, {"l2_delta": float(np.linalg.norm(updated - base))}

        def evaluate(
            self,
            parameters: list[np.ndarray],
            config: dict[str, Any],
        ) -> tuple[float, int, dict[str, Any]]:
            return 0.0, 1, {}

    return ToyClient()


def main() -> None:
    np.random.seed(42)
    bank_a = np.array([1.0, 0.2], dtype=np.float32)
    bank_b = np.array([0.5, 0.9], dtype=np.float32)

    def client_fn(context: Context) -> fl.client.Client:
        # Two virtual clients: even / odd node ids
        if int(context.node_id) % 2 == 0:
            return _client(bank_a, 0.02).to_client()
        return _client(bank_b, 0.02).to_client()

    strategy = FedAvg(
        min_fit_clients=2,
        min_available_clients=2,
        min_evaluate_clients=0,
        initial_parameters=ndarrays_to_parameters([np.zeros(2, dtype=np.float32)]),
    )

    hist = fl.simulation.start_simulation(
        client_fn=client_fn,
        num_clients=2,
        client_resources={"num_cpus": 1},
        config=fl.server.ServerConfig(num_rounds=1),
        strategy=strategy,
    )

    out = {
        "num_rounds": getattr(hist, "num_rounds", 1),
        "loss_distributed": getattr(hist, "losses_distributed", []),
        "message": "Toy FedAvg completed — only small adapter tensors are aggregated (no raw docs).",
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
