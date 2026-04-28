"""Plots for projects 1 (uniformity) and 2 (V-phi)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from picqa.analysis.phase_extraction import vphi_trace
from picqa.analysis.wafer_uniformity import add_radius_column
from picqa.io.schemas import Measurement


# --------------------------------------------------------------------- #
# Project 2: V-phi curve
# --------------------------------------------------------------------- #
def plot_vphi_curve(
    measurement: Measurement,
    output_path: str | Path,
    *,
    title: str | None = None,
) -> Path:
    """Plot V vs Δφ for a single MZM die, with linear fit and Vπ marked."""
    df = vphi_trace(measurement)
    if df.empty:
        raise ValueError("Cannot build V-phi trace (no notches found)")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))

    # Left panel: notch wavelength vs bias
    axes[0].plot(df["Bias_V"], df["Notch_nm"], "o-", lw=1.5, ms=6)
    slope, intercept = np.polyfit(df["Bias_V"], df["Notch_nm"], 1)
    bs = np.linspace(df["Bias_V"].min(), df["Bias_V"].max(), 50)
    axes[0].plot(bs, slope * bs + intercept, "--",
                 alpha=0.6, label=f"slope = {slope*1000:.1f} pm/V")
    axes[0].set_xlabel("DC Bias (V)")
    axes[0].set_ylabel("Tracked notch wavelength (nm)")
    axes[0].set_title("Notch shift vs bias")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    # Right panel: phase shift vs bias, with Vπ
    axes[1].plot(df["Bias_V"], df["dPhi_over_pi"], "o-", lw=1.5, ms=6,
                 color="tab:orange")
    s, b = np.polyfit(df["Bias_V"], df["dPhi_over_pi"], 1)
    axes[1].plot(bs, s * bs + b, "--", alpha=0.6, color="tab:orange")
    axes[1].axhline(0, color="gray", lw=0.5)
    axes[1].axhline(1, color="green", lw=0.7, ls=":", label="Δφ = π")
    axes[1].axhline(-1, color="green", lw=0.7, ls=":")
    if abs(s) > 1e-9:
        vpi = abs(1.0 / s)
        axes[1].set_title(f"V-φ relation  (Vπ = {vpi:.2f} V)")
    else:
        axes[1].set_title("V-φ relation")
    axes[1].set_xlabel("DC Bias (V)")
    axes[1].set_ylabel("Δφ / π")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    if title is None:
        title = f"V-phi characterisation: {measurement.wafer}/{measurement.die}"
    fig.suptitle(title, fontsize=12, y=1.01)
    fig.tight_layout()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_vpi_distribution(
    features_with_phase: pd.DataFrame,
    output_path: str | Path,
    *,
    title: str = "Vπ distribution across wafers",
) -> Path:
    """Box plot of Vπ per wafer (working dies only) plus a Vπ·L scatter."""
    df = features_with_phase.copy()
    if "FailedContact" in df.columns:
        df = df[~df["FailedContact"]]
    df = df.dropna(subset=["Vpi_V"])

    if df.empty:
        raise ValueError("No working dies with valid Vπ found")

    wafers = sorted(df["Wafer"].dropna().unique())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))

    # (a) Vπ box plot
    data, labels = [], []
    for w in wafers:
        sub = df[df["Wafer"] == w]
        if len(sub):
            data.append(sub["Vpi_V"].values)
            labels.append(f"{w}\n(n={len(sub)})")
    axes[0].boxplot(data, tick_labels=labels, showmeans=True)
    axes[0].set_ylabel("Vπ (V)")
    axes[0].set_title("Vπ per wafer (working dies)")
    axes[0].grid(alpha=0.3)

    # (b) Vπ vs Vπ·L scatter
    if "Vpi_L_V_cm" in df.columns and df["Vpi_L_V_cm"].notna().any():
        for w in wafers:
            sub = df[df["Wafer"] == w]
            axes[1].scatter(sub["Vpi_V"], sub["Vpi_L_V_cm"],
                            alpha=0.7, s=40, label=w)
        axes[1].set_xlabel("Vπ (V)")
        axes[1].set_ylabel("Vπ·L (V·cm)")
        axes[1].set_title("Vπ·L figure of merit")
        axes[1].legend()
        axes[1].grid(alpha=0.3)
    else:
        # Replace with ER scatter
        if "ER_at_-2V_dB" in df.columns:
            for w in wafers:
                sub = df[df["Wafer"] == w]
                axes[1].scatter(sub["Vpi_V"], sub["ER_at_-2V_dB"],
                                alpha=0.7, s=40, label=w)
            axes[1].set_xlabel("Vπ (V)")
            axes[1].set_ylabel("ER @ -2 V (dB)")
            axes[1].set_title("Vπ vs Extinction Ratio")
            axes[1].legend()
            axes[1].grid(alpha=0.3)

    fig.suptitle(title, fontsize=12, y=1.02)
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


# --------------------------------------------------------------------- #
# Project 1: uniformity
# --------------------------------------------------------------------- #
def plot_radial_dependence(
    features: pd.DataFrame,
    metric: str,
    output_path: str | Path,
    *,
    title: str | None = None,
) -> Path:
    """Scatter of metric vs die radius, color-coded by wafer.

    Adds a per-wafer mean line at each integer-rounded radius.
    """
    if metric not in features.columns:
        raise KeyError(metric)

    df = add_radius_column(features)
    if "FailedContact" in df.columns:
        df = df[~df["FailedContact"]]
    df = df.dropna(subset=[metric, "Radius"])
    if df.empty:
        raise ValueError(f"No data for {metric}")

    wafers = sorted(df["Wafer"].dropna().unique())
    cmap = plt.get_cmap("tab10")
    color_of = {w: cmap(i % 10) for i, w in enumerate(wafers)}

    fig, ax = plt.subplots(figsize=(9, 5))

    for w in wafers:
        sub = df[df["Wafer"] == w]
        ax.scatter(sub["Radius"], sub[metric], color=color_of[w],
                   alpha=0.45, s=40, label=f"{w} (n={len(sub)})")
        # Per-radius mean trendline
        means = sub.groupby(sub["Radius"].round())[metric].mean()
        ax.plot(means.index, means.values, "-", color=color_of[w], lw=2)

    ax.set_xlabel("Die radius (units of die spacing)")
    ax.set_ylabel(metric)
    ax.set_title(title or f"{metric} vs wafer radius")
    ax.legend(fontsize=8, loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_center_vs_edge(
    features: pd.DataFrame,
    metrics: list[str],
    output_path: str | Path,
    *,
    edge_radius: float = 2.5,
    title: str = "Center vs edge comparison",
) -> Path:
    """Side-by-side boxplot pairs (center vs edge) for several metrics."""
    df = features.copy()
    if "FailedContact" in df.columns:
        df = df[~df["FailedContact"]]
    df = add_radius_column(df)
    df["Region"] = np.where(df["Radius"] <= edge_radius, "center", "edge")

    n = len(metrics)
    fig, axes = plt.subplots(1, n, figsize=(4.0 * n, 4.4))
    if n == 1:
        axes = [axes]

    for ax, metric in zip(axes, metrics):
        if metric not in df.columns:
            ax.set_title(f"{metric}\n(missing)")
            continue
        center = df[df["Region"] == "center"][metric].dropna()
        edge = df[df["Region"] == "edge"][metric].dropna()
        ax.boxplot([center.values, edge.values],
                   tick_labels=[f"center\n(n={len(center)})",
                                f"edge\n(n={len(edge)})"],
                   showmeans=True)
        ax.set_ylabel(metric)
        ax.set_title(metric)
        ax.grid(alpha=0.3)

    fig.suptitle(title, fontsize=12, y=1.02)
    fig.tight_layout()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out
