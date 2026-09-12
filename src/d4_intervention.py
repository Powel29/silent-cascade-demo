"""D4 (optional) — intervention comparison: hardening a substation vs. a verification
checkpoint on the AI routing layer.

Three conditions, each run `n_runs` times with the same set of random initial failures
(paired comparison, so the only thing that varies between conditions is the intervention):

  1. baseline               — no intervention, cascade() runs as-is
  2. harden_substation      — top-ranked node from d1_criticality.csv gets capacity *= 1.5
  3. verification_checkpoint — modelled as: in `verification_checkpoint_prevention_rate`
                                fraction of runs, the initiating failure is prevented
                                entirely (repair happened before the trip); otherwise the
                                cascade runs unmodified. See config.yaml for why this
                                modelling choice was made over "delay by N steps".

Requires data/processed/graph.gpickle (build_graph.py) and outputs/d1_criticality.csv
(d1_cascade.py) to already exist.
"""

from __future__ import annotations

import copy
import pickle
import random
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import yaml

from cascade import cascade

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
OUTPUTS_DIR = REPO_ROOT / "outputs"


def load_config() -> dict[str, Any]:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_graph() -> nx.DiGraph:
    with open(PROCESSED_DIR / "graph.gpickle", "rb") as f:
        return pickle.load(f)


def load_top_critical_node() -> str:
    path = OUTPUTS_DIR / "d1_criticality.csv"
    if not path.exists():
        raise RuntimeError(f"{path} not found — run d1_cascade.py first (D4 needs its criticality ranking).")
    df = pd.read_csv(path)
    return df.iloc[0]["node_id"]


def hardened_graph(G: nx.DiGraph, node_id: str, factor: float) -> nx.DiGraph:
    H = copy.deepcopy(G)
    H.nodes[node_id]["capacity"] *= factor
    return H


def draw_random_failures(G: nx.DiGraph, n_runs: int, seed: int) -> list[str]:
    """One random substation per run, shared across all three conditions for a paired comparison."""
    rng = random.Random(seed)
    substations = sorted(n for n, d in G.nodes(data=True) if d["type"] == "substation")
    return [rng.choice(substations) for _ in range(n_runs)]


def run_condition(
    G: nx.DiGraph,
    initial_failures: list[str],
    cfg: dict[str, Any],
    prevention_rate: float = 0.0,
    prevention_seed: int = 0,
) -> list[int]:
    """Returns final people_affected for each run. `prevention_rate` > 0 implements the
    verification-checkpoint condition: that fraction of runs never fail at all."""
    rng = random.Random(prevention_seed)
    hours_per_step = cfg["assumptions"]["hours_per_step"]
    max_steps = cfg["d1"]["max_steps"]
    results = []
    for node in initial_failures:
        if prevention_rate > 0 and rng.random() < prevention_rate:
            results.append(0)
            continue
        timeline = cascade(G, [node], max_steps=max_steps, hours_per_step=hours_per_step)
        results.append(timeline[-1]["people_affected"])
    return results


def main() -> None:
    cfg = load_config()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    print("[d4_intervention] loading graph and criticality ranking...")
    G = load_graph()
    top_node = load_top_critical_node()
    print(f"[d4_intervention] hardening top-ranked node: {top_node}")

    n_runs = cfg["d4"]["n_runs"]
    seed = cfg["seed"]
    initial_failures = draw_random_failures(G, n_runs, seed)

    print(f"[d4_intervention] running {n_runs} trials x 3 conditions...")

    baseline_results = run_condition(G, initial_failures, cfg)
    print(f"[d4_intervention] baseline: mean people_affected = {sum(baseline_results)/n_runs:,.0f}")

    H = hardened_graph(G, top_node, factor=1.5)
    hardened_results = run_condition(H, initial_failures, cfg)
    print(f"[d4_intervention] harden_substation: mean people_affected = {sum(hardened_results)/n_runs:,.0f}")

    prevention_rate = cfg["d4"]["verification_checkpoint_prevention_rate"]
    checkpoint_results = run_condition(
        G, initial_failures, cfg, prevention_rate=prevention_rate, prevention_seed=seed + 1
    )
    print(f"[d4_intervention] verification_checkpoint: mean people_affected = {sum(checkpoint_results)/n_runs:,.0f}")

    costs = cfg["assumptions"]["cost_inr"]
    conditions = [
        ("Baseline\n(no intervention)", baseline_results, 0),
        ("Harden substation", hardened_results, costs["harden_substation"]),
        ("Verification checkpoint", checkpoint_results, costs["verification_checkpoint"]),
    ]

    summary = pd.DataFrame(
        [
            {
                "condition": label.replace("\n", " "),
                "mean_people_affected": sum(vals) / n_runs,
                "cost_inr": cost,
            }
            for label, vals, cost in conditions
        ]
    )
    summary_path = OUTPUTS_DIR / "d4_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"[d4_intervention] wrote {summary_path}")
    print(summary.to_string(index=False))

    plot_comparison(conditions, n_runs, OUTPUTS_DIR / "d4_comparison.png")

    print("\n[d4_intervention] === sensitivity sweep: is 31% reduction fragile to the 40% assumption? ===")
    rates = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    hardened_mean = sum(hardened_results) / n_runs
    sweep = sensitivity_sweep(G, initial_failures, cfg, rates, seed)
    sweep_path = OUTPUTS_DIR / "d4_sensitivity.csv"
    sweep.to_csv(sweep_path, index=False)
    print(f"[d4_intervention] wrote {sweep_path}")
    print(sweep.to_string(index=False))
    crossover = sweep[sweep.mean_people_affected <= hardened_mean]
    if not crossover.empty:
        x = crossover.iloc[0]["prevention_rate"]
        print(f"[d4_intervention] checkpoint beats hardening down to prevention_rate={x:.0%} "
              f"(assumption used elsewhere is {prevention_rate:.0%})")
    else:
        print("[d4_intervention] NOTE: checkpoint does NOT beat hardening anywhere in the swept "
              "range — report this honestly if it occurs, do not hide it.")
    plot_sensitivity(sweep, hardened_mean, prevention_rate, OUTPUTS_DIR / "d4_sensitivity.png")


def sensitivity_sweep(
    G: nx.DiGraph,
    initial_failures: list[str],
    cfg: dict[str, Any],
    rates: list[float],
    seed: int,
) -> pd.DataFrame:
    """Re-run the verification-checkpoint condition across a range of prevention rates.

    The headline 40% prevention rate is an assumption (see config.yaml); this shows whether
    the "checkpoint beats hardening" conclusion is a robust finding across the plausible range
    or an artifact of that one chosen number.
    """
    n_runs = len(initial_failures)
    rows = []
    for rate in rates:
        results = run_condition(G, initial_failures, cfg, prevention_rate=rate, prevention_seed=seed + 1)
        rows.append({"prevention_rate": rate, "mean_people_affected": sum(results) / n_runs})
    return pd.DataFrame(rows)


def plot_sensitivity(sweep: pd.DataFrame, hardened_mean: float, headline_rate: float, out_path: Path | None) -> plt.Figure:
    """Line chart: checkpoint's mean impact vs. prevention rate, with hardening as a reference line."""
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    ax.plot(sweep.prevention_rate * 100, sweep.mean_people_affected, marker="o", color="#34a853", label="Verification checkpoint")
    ax.axhline(hardened_mean, color="#4285f4", linestyle="--", label=f"Harden substation ({hardened_mean:,.0f})")
    ax.axvline(headline_rate * 100, color="#9aa0a6", linestyle=":", label=f"Headline assumption ({headline_rate:.0%})")
    ax.set_xlabel("Verification checkpoint prevention rate (%)", fontsize=12)
    ax.set_ylabel("Mean people affected", fontsize=12)
    ax.set_title("Sensitivity: does the checkpoint still win at lower prevention rates?", fontsize=14)
    ax.legend(fontsize=10)
    fig.tight_layout()
    if out_path is not None:
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"[d4_intervention] wrote {out_path}")
    return fig


def plot_comparison(conditions: list[tuple[str, list[int], float]], n_runs: int, out_path: Path | None) -> plt.Figure:
    """Horizontal bar chart of mean impact per condition. Saves to out_path if given; returns the figure."""
    labels = [c[0] for c in conditions]
    means = [sum(c[1]) / n_runs for c in conditions]
    costs = [c[2] for c in conditions]
    colors = ["#9aa0a6", "#4285f4", "#34a853"]

    fig, ax = plt.subplots(figsize=(12, 6), dpi=150)
    y = range(len(labels))
    bars = ax.barh(list(y), means, color=colors)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=13)
    ax.invert_yaxis()
    ax.set_xlabel(f"Mean people affected (n={n_runs} runs, ILLUSTRATIVE cost assumptions)", fontsize=12)
    ax.set_title("Intervention comparison: mean cascade impact", fontsize=15)

    for bar, mean, cost in zip(bars, means, costs):
        label = f"{mean:,.0f} people" + (f"  |  ~₹{cost:,.0f}" if cost else "  |  ₹0")
        ax.text(bar.get_width() + max(means) * 0.01, bar.get_y() + bar.get_height() / 2, label, va="center", fontsize=11)

    fig.tight_layout()
    if out_path is not None:
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"[d4_intervention] wrote {out_path}")
    return fig


if __name__ == "__main__":
    main()
