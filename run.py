"""Entry point for single-run and multi-regime experiments."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from institutions import REGIMES, RegimeName
from model import LogisticsCollaborationModel


def _run_once(
    institution: RegimeName,
    rounds: int,
    seed: int | None,
) -> tuple[dict, pd.DataFrame]:
    model = LogisticsCollaborationModel(
        institution=institution,
        n_rounds=rounds,
        seed=seed,
    )
    model.run_model()
    summary = model.get_summary_metrics()
    trace = model.datacollector.get_model_vars_dataframe().copy()
    trace["institution"] = institution
    return summary, trace


def run_single(
    institution: RegimeName,
    rounds: int,
    seed: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary, trace = _run_once(institution, rounds, seed)
    summary_df = pd.DataFrame([summary])
    return summary_df, trace


def run_batch(
    institutions: Iterable[RegimeName],
    rounds: int,
    replications: int,
    seed: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries: List[dict] = []
    traces: List[pd.DataFrame] = []

    for regime in institutions:
        for replication in range(replications):
            run_seed = None if seed is None else (seed + replication * 100 + REGIMES.index(regime))
            summary, trace = _run_once(regime, rounds, run_seed)
            summary["replication"] = replication
            trace = trace.copy()
            trace["replication"] = replication
            summaries.append(summary)
            traces.append(trace)

    return pd.DataFrame(summaries), pd.concat(traces, ignore_index=True)


def _print_summary(summary_df: pd.DataFrame, title: str) -> None:
    print("\n" + title)
    print("-" * len(title))
    with pd.option_context("display.width", 140, "display.max_columns", None):
        print(summary_df.round(3).to_string(index=False))


def _save_outputs(
    summary_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    output_dir: Path,
    prefix: str,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"{prefix}_summary.csv"
    trace_path = output_dir / f"{prefix}_trace.csv"
    summary_df.to_csv(summary_path, index=False)
    trace_df.to_csv(trace_path, index=False)
    return summary_path, trace_path


def _plot_batch(trace_df: pd.DataFrame, output_dir: Path) -> Path:
    import matplotlib.pyplot as plt

    grouped = (
        trace_df.groupby(["institution", "round"], as_index=False)[
            ["collaboration_rate", "trust_a", "trust_b"]
        ]
        .mean()
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    for regime in REGIMES:
        subset = grouped[grouped["institution"] == regime]
        axes[0].plot(subset["round"], subset["collaboration_rate"], label=regime)
        avg_trust = (subset["trust_a"] + subset["trust_b"]) / 2.0
        axes[1].plot(subset["round"], avg_trust, label=regime)

    axes[0].set_title("Collaboration Rate")
    axes[0].set_xlabel("Round")
    axes[0].set_ylabel("Rate")

    axes[1].set_title("Average Trust")
    axes[1].set_xlabel("Round")
    axes[1].set_ylabel("Trust")
    axes[1].set_ylim(0.0, 1.0)

    for ax in axes:
        ax.grid(alpha=0.3)
    axes[1].legend(loc="best")
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "batch_trajectories.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return plot_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mesa + norms-games research prototype for logistics collaboration."
    )
    parser.add_argument(
        "--institution",
        choices=list(REGIMES),
        default="baseline",
        help="Institution to use in single-run mode.",
    )
    parser.add_argument("--rounds", type=int, default=100, help="Number of rounds per run.")
    parser.add_argument(
        "--replications",
        type=int,
        default=5,
        help="Replications per institution in batch mode.",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "batch", "both"],
        default="both",
        help="Whether to run one institution, all institutions, or both.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Base random seed.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs",
        help="Directory where CSV/plots are written.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="If set, write a PNG plot for batch trajectories.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.rounds <= 0:
        raise ValueError("--rounds must be a positive integer.")
    if args.replications <= 0:
        raise ValueError("--replications must be a positive integer.")

    if args.mode in ("single", "both"):
        single_summary, single_trace = run_single(
            institution=args.institution,
            rounds=args.rounds,
            seed=args.seed,
        )
        _print_summary(single_summary, "Single-Run Summary")
        summary_path, trace_path = _save_outputs(
            single_summary,
            single_trace,
            args.output_dir,
            prefix=f"single_{args.institution}",
        )
        print("\nSaved single-run CSV files:")
        print(summary_path)
        print(trace_path)

    if args.mode in ("batch", "both"):
        batch_summary, batch_trace = run_batch(
            institutions=REGIMES,
            rounds=args.rounds,
            replications=args.replications,
            seed=args.seed,
        )
        agg = (
            batch_summary.groupby("institution", as_index=False)[
                ["collaboration_rate", "cash_a", "cash_b", "trust_a", "trust_b", "mean_welfare"]
            ]
            .mean()
            .sort_values("collaboration_rate", ascending=False)
        )
        _print_summary(agg, "Batch Mean Summary (Across Replications)")
        summary_path, trace_path = _save_outputs(
            batch_summary,
            batch_trace,
            args.output_dir,
            prefix="batch_all_institutions",
        )
        print("\nSaved batch CSV files:")
        print(summary_path)
        print(trace_path)

        if args.plot:
            plot_path = _plot_batch(batch_trace, args.output_dir)
            print("\nSaved batch plot:")
            print(plot_path)


if __name__ == "__main__":
    main()
