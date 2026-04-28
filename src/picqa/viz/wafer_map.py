"""Wafer-map plotting."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _draw_wafer_map(
    ax: plt.Axes,
    df: pd.DataFrame,
    metric: str,
    title: str,
    *,
    vmin: float | None = None,
    vmax: float | None = None,
    annotate: bool = True,
) -> None:
    cols = sorted(df["DieCol"].unique())
    rows = sorted(df["DieRow"].unique())
    grid = np.full((len(rows), len(cols)), np.nan)
    for _, r in df.iterrows():
        gc = cols.index(r["DieCol"])
        gr = rows.index(r["DieRow"])
        grid[gr, gc] = r[metric]

    im = ax.imshow(
        grid,
        origin="lower",
        vmin=vmin,
        vmax=vmax,
        cmap="viridis",
        extent=[min(cols) - 0.5, max(cols) + 0.5,
                min(rows) - 0.5, max(rows) + 0.5],
        aspect="equal",
    )
    ax.set_xticks(cols)
    ax.set_yticks(rows)
    ax.set_xlabel("Die Column")
    ax.set_ylabel("Die Row")
    ax.set_title(title, fontsize=9)
    plt.colorbar(im, ax=ax, fraction=0.04)
    if annotate:
        for _, r in df.iterrows():
            v = r[metric]
            if not np.isnan(v):
                ax.text(
                    r["DieCol"], r["DieRow"], f"{v:.1f}",
                    ha="center", va="center",
                    fontsize=6, color="white",
                )


def plot_wafermap(
    features: pd.DataFrame,
    metric: str,
    output_path: str | Path,
    *,
    title: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
) -> Path:
    """Plot a single wafer-map for one metric (uses all rows in ``features``)."""
    if metric not in features.columns:
        raise KeyError(f"Metric '{metric}' not in DataFrame columns: {list(features.columns)}")

    fig, ax = plt.subplots(figsize=(5.5, 4.8))
    _draw_wafer_map(ax, features, metric, title or metric, vmin=vmin, vmax=vmax)
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_wafermap_grid(
    features: pd.DataFrame,
    metrics: list[str],
    output_path: str | Path,
    *,
    group_by: list[str] | None = None,
) -> Path:
    """Grid of wafer-maps: rows = groups (e.g. wafer/session), cols = metrics."""
    if group_by is None:
        group_by = ["Wafer", "Session"]
    groups: list[tuple] = sorted({tuple(r[c] for c in group_by) for _, r in features.iterrows()})
    nrows = len(groups)
    ncols = len(metrics)
    if nrows == 0 or ncols == 0:
        raise ValueError("No groups or metrics to plot")

    fig, axes = plt.subplots(nrows, ncols, figsize=(5.5 * ncols, 3.6 * nrows))
    if nrows == 1 and ncols == 1:
        axes = np.array([[axes]])
    elif nrows == 1:
        axes = axes[None, :]
    elif ncols == 1:
        axes = axes[:, None]

    for i, key in enumerate(groups):
        mask = np.ones(len(features), dtype=bool)
        for col, val in zip(group_by, key):
            mask &= (features[col] == val)
        sub = features[mask]
        for j, metric in enumerate(metrics):
            label = " / ".join(str(v) for v in key)
            _draw_wafer_map(axes[i, j], sub, metric, f"{label}: {metric}")

    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out
