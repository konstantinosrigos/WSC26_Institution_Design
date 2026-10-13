"""Run multiple seeded simulations and plot per-round metric averages."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from institutions import REGIMES, RegimeName
from model import LogisticsCollaborationModel


def _run_once(institution: RegimeName, rounds: int, seed: int) -> pd.DataFrame:
    model = LogisticsCollaborationModel(institution=institution, n_rounds=rounds, seed=seed)
    model.run_model()
    trace = model.datacollector.get_model_vars_dataframe().copy()
    trace["seed"] = seed
    return trace


def _parse_seeds(args: argparse.Namespace) -> list[int]:
    if args.seeds:
        parsed = [int(token.strip()) for token in args.seeds.split(",") if token.strip()]
        if not parsed:
            raise ValueError("--seeds was provided but no valid integers were parsed.")
        return parsed
    return [args.base_seed + i * args.seed_step for i in range(args.num_seeds)]


def _validate_args(args: argparse.Namespace) -> None:
    if args.rounds <= 0:
        raise ValueError("--rounds must be a positive integer.")
    if args.num_seeds <= 0:
        raise ValueError("--num-seeds must be a positive integer.")
    if args.seed_step <= 0:
        raise ValueError("--seed-step must be a positive integer.")


def _metric_columns(trace_df: pd.DataFrame, requested: Sequence[str] | None) -> list[str]:
    numeric_columns = [
        name
        for name in trace_df.select_dtypes(include="number").columns
        if name not in {"round", "seed"}
    ]
    if requested is None:
        return numeric_columns

    missing = [name for name in requested if name not in numeric_columns]
    if missing:
        raise ValueError(
            "Unknown metric(s): "
            + ", ".join(missing)
            + ". Available metrics: "
            + ", ".join(numeric_columns)
        )
    return list(requested)


def _regime_colors(regimes: Sequence[str]) -> dict[str, tuple[float, float, float, float]]:
    import matplotlib.pyplot as plt

    cmap = plt.get_cmap("tab10")
    return {regime: cmap(index % cmap.N) for index, regime in enumerate(regimes)}


def _plot_metrics(
    trace_df: pd.DataFrame,
    mean_df: pd.DataFrame,
    metrics: Iterable[str],
    output_path: Path,
    average_color: str | tuple[float, float, float, float] = "#1f77b4",
    average_label: str = "Average",
) -> None:
    import matplotlib.pyplot as plt

    metric_list = list(metrics)
    ncols = 2
    nrows = math.ceil(len(metric_list) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, max(4, 3.4 * nrows)), squeeze=False)
    axis_list = list(axes.ravel())

    seeds = sorted(trace_df["seed"].unique())
    for index, metric in enumerate(metric_list):
        ax = axis_list[index]
        for seed in seeds:
            subset = trace_df[trace_df["seed"] == seed]
            ax.plot(subset["round"], subset[metric], color="0.45", alpha=0.28, linewidth=1.0)
        ax.plot(
            mean_df["round"],
            mean_df[metric],
            color=average_color,
            linewidth=2.4,
            label=average_label,
        )
        ax.set_title(metric.replace("_", " ").title())
        ax.set_xlabel("Round")
        ax.grid(alpha=0.25)
        if metric.startswith("trust_"):
            ax.set_ylim(0.0, 1.0)
        if index == 0:
            ax.legend(loc="best")

    for index in range(len(metric_list), len(axis_list)):
        axis_list[index].set_visible(False)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _plot_combined_regimes(
    mean_df: pd.DataFrame,
    metrics: Iterable[str],
    output_path: Path,
    regimes: Sequence[str],
    colors: dict[str, tuple[float, float, float, float]],
) -> None:
    import matplotlib.pyplot as plt

    metric_list = list(metrics)
    ncols = 2
    nrows = math.ceil(len(metric_list) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, max(4, 3.4 * nrows)), squeeze=False)
    axis_list = list(axes.ravel())

    for index, metric in enumerate(metric_list):
        ax = axis_list[index]
        for regime in regimes:
            subset = mean_df[mean_df["institution"] == regime]
            ax.plot(
                subset["round"],
                subset[metric],
                color=colors[regime],
                linewidth=2.2,
                label=regime,
            )
        ax.set_title(metric.replace("_", " ").title())
        ax.set_xlabel("Round")
        ax.grid(alpha=0.25)
        if metric.startswith("trust_"):
            ax.set_ylim(0.0, 1.0)
        if index == 0:
            ax.legend(loc="best")

    for index in range(len(metric_list), len(axis_list)):
        axis_list[index].set_visible(False)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run simulations across seeds and plot per-round metric averages."
    )
    parser.add_argument(
        "--institution",
        choices=list(REGIMES) + ["all"],
        default="baseline",
        help="One institution, or 'all' to run every regime.",
    )
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--base-seed", type=int, default=42)
    parser.add_argument("--num-seeds", type=int, default=20)
    parser.add_argument("--seed-step", type=int, default=1)
    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="Comma-separated explicit seeds. Overrides --base-seed/--num-seeds/--seed-step.",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=None,
        help="Optional explicit metric columns to plot.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Output prefix. Defaults to multi_seed_<institution>.",
    )
    return parser.parse_args()


def main() -> None:
    """
    run with
    py -3 -m multi_seed_plot --institution all --rounds 200 --num-seeds 30 --base-seed 42
    Returns
    -------

    """
    args = parse_args()
    _validate_args(args)
    seeds = _parse_seeds(args)
    regimes = list(REGIMES) if args.institution == "all" else [args.institution]
    colors = _regime_colors(regimes)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    trace_by_regime: dict[str, pd.DataFrame] = {}
    mean_by_regime: dict[str, pd.DataFrame] = {}
    metric_columns: list[str] | None = None
    saved_paths: list[Path] = []

    for regime in regimes:
        traces = [_run_once(regime, args.rounds, seed) for seed in seeds]
        trace_df = pd.concat(traces, ignore_index=True)
        metrics = _metric_columns(trace_df, args.metrics if metric_columns is None else metric_columns)
        metric_columns = metrics
        mean_df = trace_df.groupby("round", as_index=False)[metrics].mean()
        mean_df["institution"] = regime

        if args.institution == "all":
            regime_prefix = (
                f"{args.prefix}_{regime}"
                if args.prefix is not None
                else f"multi_seed_{regime}"
            )
        else:
            regime_prefix = args.prefix or f"multi_seed_{regime}"

        trace_path = args.output_dir / f"{regime_prefix}_trace.csv"
        mean_path = args.output_dir / f"{regime_prefix}_mean_trace.csv"
        plot_path = args.output_dir / f"{regime_prefix}_metrics.png"

        trace_df.to_csv(trace_path, index=False)
        mean_df.to_csv(mean_path, index=False)
        _plot_metrics(
            trace_df,
            mean_df,
            metrics,
            plot_path,
            average_color=colors[regime],
            average_label=f"{regime} average",
        )

        trace_by_regime[regime] = trace_df
        mean_by_regime[regime] = mean_df
        saved_paths.extend([trace_path, mean_path, plot_path])

    if len(regimes) > 1 and metric_columns is not None:
        combined_trace = pd.concat(
            [trace_by_regime[regime] for regime in regimes],
            ignore_index=True,
        )
        combined_mean = pd.concat(
            [mean_by_regime[regime] for regime in regimes],
            ignore_index=True,
        )

        combined_prefix = args.prefix or "multi_seed_all_regimes"
        combined_trace_path = args.output_dir / f"{combined_prefix}_trace.csv"
        combined_mean_path = args.output_dir / f"{combined_prefix}_mean_trace.csv"
        combined_plot_path = args.output_dir / f"{combined_prefix}_combined_metrics.png"

        combined_trace.to_csv(combined_trace_path, index=False)
        combined_mean.to_csv(combined_mean_path, index=False)
        _plot_combined_regimes(
            combined_mean,
            metric_columns,
            combined_plot_path,
            regimes=regimes,
            colors=colors,
        )
        saved_paths.extend([combined_trace_path, combined_mean_path, combined_plot_path])

    print("\nSaved files:")
    for path in saved_paths:
        print(path)
    print(f"\nRegimes run ({len(regimes)}): {', '.join(regimes)}")
    print(f"Seeds used ({len(seeds)}): {seeds}")
    if metric_columns is not None:
        print(f"Metrics plotted ({len(metric_columns)}): {', '.join(metric_columns)}")


if __name__ == "__main__":
    main()
