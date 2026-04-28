"""Wafer-level uniformity analysis (Project 1).

Quantifies how device performance varies with position on the wafer:

* **Radial binning** — split dies into "center" / "edge" and compare
* **Per-radius statistics** — median and CV (coefficient of variation) at
  each radius
* **FSR-to-thickness mapping** — convert FSR variation into an estimate of
  waveguide effective-index variation, which in turn reflects geometry
  variation (width / thickness)
* **Yield map by region** — pass-rate as a function of die position

These are deliberately simple, robust statistics rather than full
spatial-correlation models, on the grounds that the dataset has 14 dies
per wafer (too few for variograms but plenty for radial trends).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_radius_column(features: pd.DataFrame) -> pd.DataFrame:
    """Add a ``Radius`` column = sqrt(DieCol² + DieRow²) in die units.

    The wafer center is assumed to be at (0, 0) in die-coordinate space.
    """
    out = features.copy()
    if {"DieCol", "DieRow"}.issubset(out.columns):
        out["Radius"] = np.hypot(out["DieCol"].astype(float),
                                 out["DieRow"].astype(float))
    else:
        out["Radius"] = np.nan
    return out


def add_region_column(features: pd.DataFrame, *, edge_radius: float = 2.5) -> pd.DataFrame:
    """Tag each die as ``'center'`` or ``'edge'`` based on radius threshold.

    With 14 dies per wafer arranged on a roughly disk-shaped grid, a
    threshold of 2.5 die-units puts ~6 dies in 'center' and ~8 in 'edge'.
    """
    out = features.copy() if "Radius" in features.columns else add_radius_column(features)
    out["Region"] = np.where(out["Radius"] <= edge_radius, "center", "edge")
    return out


def center_vs_edge(
    features: pd.DataFrame,
    metric: str,
    *,
    edge_radius: float = 2.5,
    group_by: list[str] | None = None,
) -> pd.DataFrame:
    """Compare a metric between center and edge dies.

    Returns one row per group (or one row total if ``group_by`` is None) with
    medians, CVs, and the difference. The CV (coefficient of variation) is
    ``std / |mean|`` reported as a percentage.
    """
    if metric not in features.columns:
        raise KeyError(f"Metric {metric!r} not in DataFrame columns")

    df = add_region_column(features, edge_radius=edge_radius)

    def _stats(sub: pd.DataFrame) -> dict:
        center = sub[sub["Region"] == "center"][metric].dropna()
        edge = sub[sub["Region"] == "edge"][metric].dropna()
        center_med = float(center.median()) if len(center) else float("nan")
        edge_med = float(edge.median()) if len(edge) else float("nan")
        center_cv = float(center.std() / abs(center.mean()) * 100) \
            if len(center) > 1 and center.mean() != 0 else float("nan")
        edge_cv = float(edge.std() / abs(edge.mean()) * 100) \
            if len(edge) > 1 and edge.mean() != 0 else float("nan")
        return {
            "n_center": len(center),
            "n_edge": len(edge),
            "center_median": center_med,
            "edge_median": edge_med,
            "center_CV_pct": center_cv,
            "edge_CV_pct": edge_cv,
            "delta_center_minus_edge": center_med - edge_med,
        }

    if not group_by:
        return pd.DataFrame([{"metric": metric, **_stats(df)}])

    rows: list[dict] = []
    for keys, sub in df.groupby(group_by, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        rows.append({**dict(zip(group_by, keys)),
                     "metric": metric,
                     **_stats(sub)})
    return pd.DataFrame(rows)


def per_radius_stats(
    features: pd.DataFrame,
    metric: str,
    *,
    group_by: list[str] | None = None,
) -> pd.DataFrame:
    """Median and CV of a metric for each integer-bucketed radius.

    Useful for plotting performance vs radius.
    """
    if metric not in features.columns:
        raise KeyError(f"Metric {metric!r} not in DataFrame columns")
    df = add_radius_column(features)
    df["RadiusBin"] = df["Radius"].round().astype("Int64")

    keys = (group_by or []) + ["RadiusBin"]
    rows: list[dict] = []
    for keyvals, sub in df.groupby(keys, dropna=False):
        if not isinstance(keyvals, tuple):
            keyvals = (keyvals,)
        vals = sub[metric].dropna()
        if vals.empty:
            continue
        mean = float(vals.mean())
        std = float(vals.std()) if len(vals) > 1 else 0.0
        cv = (std / abs(mean) * 100) if mean != 0 else float("nan")
        rows.append({
            **dict(zip(keys, keyvals)),
            "metric": metric,
            "n": int(len(vals)),
            "median": float(vals.median()),
            "mean": mean,
            "std": std,
            "CV_pct": cv,
        })
    return pd.DataFrame(rows)


def fsr_to_index_variation(
    features: pd.DataFrame,
    *,
    design_wavelength_nm: float = 1310.0,
    group_by: list[str] | None = None,
) -> pd.DataFrame:
    """Estimate effective-index variation from FSR variation.

    For an unbalanced MZ interferometer, FSR ≈ λ² / (n_g · ΔL) where ΔL is
    the arm length difference and n_g the group index. So the relative
    variation in n_g (and by extension in waveguide geometry, since n_g
    depends on width and thickness) is::

        Δn_g / n_g  ≈  -ΔFSR / FSR

    This function reports σ_FSR / FSR_mean (in %) per group, which serves
    as a proxy for waveguide-geometry variation across the population.
    """
    if "FSR_nm" not in features.columns:
        raise KeyError("FSR_nm column required")

    rows: list[dict] = []
    if not group_by:
        vals = features["FSR_nm"].dropna()
        if not vals.empty:
            rel = float(vals.std() / abs(vals.mean()) * 100)
            rows.append({
                "n": len(vals),
                "FSR_mean_nm": float(vals.mean()),
                "FSR_std_nm": float(vals.std()),
                "FSR_relative_variation_pct": rel,
                "Implied_index_variation_pct": rel,
            })
    else:
        for keys, sub in features.groupby(group_by, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            vals = sub["FSR_nm"].dropna()
            if vals.empty:
                continue
            mean = float(vals.mean())
            std = float(vals.std()) if len(vals) > 1 else 0.0
            rel = (std / abs(mean) * 100) if mean != 0 else float("nan")
            rows.append({
                **dict(zip(group_by, keys)),
                "n": len(vals),
                "FSR_mean_nm": mean,
                "FSR_std_nm": std,
                "FSR_relative_variation_pct": rel,
                "Implied_index_variation_pct": rel,
            })
    return pd.DataFrame(rows)


def iv_uniformity(
    features: pd.DataFrame,
    *,
    metric: str = "I_at_-1V_pA",
    group_by: list[str] | None = None,
) -> pd.DataFrame:
    """Uniformity statistics for an IV-derived metric.

    Reports mean, std, CV, min, max, and a robust median + MAD (which is
    insensitive to the failed-contact outliers that completely break the
    parametric stats).
    """
    if metric not in features.columns:
        raise KeyError(f"Metric {metric!r} not in DataFrame columns")

    rows: list[dict] = []

    def _row(sub: pd.DataFrame, prefix: dict) -> dict | None:
        vals = sub[metric].dropna()
        if vals.empty:
            return None
        med = float(vals.median())
        mad = float(np.median(np.abs(vals - med)))
        return {
            **prefix,
            "n": int(len(vals)),
            "mean": float(vals.mean()),
            "std": float(vals.std()) if len(vals) > 1 else 0.0,
            "CV_pct": float(vals.std() / abs(vals.mean()) * 100)
                if len(vals) > 1 and vals.mean() != 0 else float("nan"),
            "min": float(vals.min()),
            "max": float(vals.max()),
            "median": med,
            "mad_std": 1.4826 * mad,
        }

    if not group_by:
        r = _row(features, {})
        if r:
            rows.append(r)
    else:
        for keys, sub in features.groupby(group_by, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            r = _row(sub, dict(zip(group_by, keys)))
            if r:
                rows.append(r)

    return pd.DataFrame(rows)
