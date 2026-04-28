"""Multi-panel process summary figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from picqa.analysis.outlier import flag_failed_contacts


def plot_summary(features: pd.DataFrame, output_path: str | Path) -> Path:
    """Six-panel process characterisation summary for MZM features.

    The panels are:
    a) tuning efficiency boxplot per wafer (working only)
    b) FSR scatter per wafer
    c) leakage current boxplot (log y)
    d) peak IL boxplot
    e) notch wavelength scatter
    f) tuning vs leakage scatter
    """
    df = flag_failed_contacts(features)
    df["IsWorking"] = ~df["FailedContact"]

    fig = plt.figure(figsize=(13, 9))
    gs = fig.add_gridspec(2, 3, hspace=0.45, wspace=0.32)

    wafers = sorted(df["Wafer"].dropna().unique())

    def _box(ax, data, labels, ylabel, title, log=False):
        if not data:
            ax.set_title(f"{title} (no data)")
            return
        ax.boxplot(data, tick_labels=labels, showmeans=True)
        if log:
            ax.set_yscale("log")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(alpha=0.3, which="both" if log else "major")

    # (a)
    ax = fig.add_subplot(gs[0, 0])
    data, labels = [], []
    for w in wafers:
        sub = df[(df["Wafer"] == w) & df["IsWorking"]]
        if len(sub):
            data.append(sub["dLambda_dV_pm_per_V"].abs().values)
            labels.append(f"{w}\n(n={len(sub)})")
    _box(ax, data, labels, "|dλ/dV| (pm/V)", "MZM tuning efficiency (working only)")

    # (b)
    ax = fig.add_subplot(gs[0, 1])
    for w in wafers:
        sub = df[df["Wafer"] == w]
        if len(sub):
            ax.scatter([w] * len(sub), sub["FSR_nm"], alpha=0.6, s=30)
            ax.errorbar([w], [sub["FSR_nm"].median()],
                        yerr=[sub["FSR_nm"].std()],
                        fmt="_", color="red", capsize=8, lw=2)
    ax.set_ylabel("FSR (nm)")
    ax.set_title("Free Spectral Range across wafers")
    ax.grid(alpha=0.3)

    # (c)
    ax = fig.add_subplot(gs[0, 2])
    data, labels = [], []
    for w in wafers:
        sub = df[(df["Wafer"] == w) & df["IsWorking"]]
        if len(sub):
            data.append(np.abs(sub["I_at_-1V_pA"].values) + 1)
            labels.append(f"{w}\n(n={len(sub)})")
    _box(ax, data, labels, "|I| at -1V (pA)", "Reverse-bias leakage", log=True)

    # (d)
    ax = fig.add_subplot(gs[1, 0])
    data, labels = [], []
    for w in wafers:
        sub = df[df["Wafer"] == w]
        data.append(sub["PeakIL_near_1310_dB"].dropna().values)
        labels.append(f"{w}\n(n={len(sub)})")
    _box(ax, data, labels, "Peak IL near 1310 nm (dB)",
         "Insertion loss near design wavelength")

    # (e)
    ax = fig.add_subplot(gs[1, 1])
    for w in wafers:
        sub = df[df["Wafer"] == w]
        ax.scatter([w] * len(sub), sub["Notch_at_0V_nm"], alpha=0.6, s=30)
    ax.set_ylabel("Reference notch wavelength (nm)")
    ax.set_title("Notch wavelength near 1310 nm @ 0 V")
    ax.grid(alpha=0.3)

    # (f)
    ax = fig.add_subplot(gs[1, 2])
    markers = ["o", "s", "^", "D", "v", "P", "X"]
    for w, marker in zip(wafers, markers):
        sub = df[(df["Wafer"] == w) & df["IsWorking"]]
        ax.scatter(np.abs(sub["I_at_-1V_pA"]), np.abs(sub["dLambda_dV_pm_per_V"]),
                   marker=marker, label=w, alpha=0.7, s=40)
    ax.set_xscale("log")
    ax.set_xlabel("|I| at -1 V (pA)")
    ax.set_ylabel("|dλ/dV| (pm/V)")
    ax.set_title("Tuning efficiency vs leakage")
    ax.legend()
    ax.grid(alpha=0.3, which="both")

    fig.suptitle("MZ Modulator process characterization summary",
                 fontsize=13, y=0.995)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out
