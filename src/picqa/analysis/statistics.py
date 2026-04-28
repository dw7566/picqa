"""Robust statistics utilities for feature DataFrames."""

from __future__ import annotations

import numpy as np
import pandas as pd


def robust_summary(values: pd.Series) -> dict[str, float]:
    """Return median and 1.4826·MAD as a robust mean/std proxy.

    NaNs are dropped. If the series is empty after dropping, both stats are
    ``nan``.
    """
    s = values.dropna()
    if s.empty:
        return {"median": float("nan"), "mad_std": float("nan"), "n": 0}
    med = float(np.median(s))
    mad = float(np.median(np.abs(s - med)))
    return {"median": med, "mad_std": 1.4826 * mad, "n": int(len(s))}


def per_group_stats(
    df: pd.DataFrame,
    group_by: list[str],
    metrics: list[str],
) -> pd.DataFrame:
    """Compute robust median/MAD for each metric within each group.

    Returns a long-format DataFrame: ``[*group_by, metric, median, mad_std, n]``.
    """
    rows: list[dict] = []
    if df.empty:
        return pd.DataFrame(columns=[*group_by, "metric", "median", "mad_std", "n"])

    for keys, sub in df.groupby(group_by, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = dict(zip(group_by, keys))
        for metric in metrics:
            if metric not in sub.columns:
                continue
            stats = robust_summary(sub[metric])
            rows.append({**base, "metric": metric, **stats})
    return pd.DataFrame(rows)
