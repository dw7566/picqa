"""Tests for picqa.analysis.statistics."""

from __future__ import annotations

import math

import pandas as pd

from picqa.analysis.statistics import per_group_stats, robust_summary


def test_robust_summary_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = robust_summary(s)
    assert out["median"] == 3.0
    assert out["n"] == 5
    assert out["mad_std"] > 0


def test_robust_summary_drops_nan():
    s = pd.Series([1.0, float("nan"), 3.0])
    out = robust_summary(s)
    assert out["n"] == 2
    assert out["median"] == 2.0


def test_robust_summary_empty():
    out = robust_summary(pd.Series([], dtype=float))
    assert math.isnan(out["median"])
    assert out["n"] == 0


def test_per_group_stats_groups_correctly():
    df = pd.DataFrame(
        [
            {"Wafer": "A", "FSR_nm": 9.8},
            {"Wafer": "A", "FSR_nm": 9.9},
            {"Wafer": "B", "FSR_nm": 9.7},
        ]
    )
    out = per_group_stats(df, group_by=["Wafer"], metrics=["FSR_nm"])
    assert len(out) == 2
    a = out[out["Wafer"] == "A"].iloc[0]
    assert a["n"] == 2
    assert abs(a["median"] - 9.85) < 1e-9


def test_per_group_stats_skips_unknown_metrics():
    df = pd.DataFrame([{"Wafer": "A", "FSR_nm": 9.8}])
    out = per_group_stats(df, group_by=["Wafer"], metrics=["FSR_nm", "Nonexistent"])
    assert len(out) == 1
    assert out.iloc[0]["metric"] == "FSR_nm"


def test_per_group_stats_empty_input():
    df = pd.DataFrame(columns=["Wafer", "FSR_nm"])
    out = per_group_stats(df, group_by=["Wafer"], metrics=["FSR_nm"])
    assert out.empty
