"""Tests for wafer-uniformity and phase-extraction modules."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from picqa.analysis.phase_extraction import (
    parse_phaseshifter_length_um,
    voltage_to_phase,
    vpi_from_slope,
)
from picqa.analysis.wafer_uniformity import (
    add_radius_column,
    add_region_column,
    center_vs_edge,
    fsr_to_index_variation,
    iv_uniformity,
    per_radius_stats,
)


# --------------------------- fixtures --------------------------- #
@pytest.fixture
def sample_features():
    """Synthetic features with a clear center-vs-edge gradient."""
    rows = []
    for col in [-2, -1, 0, 1, 2]:
        for row in [-2, -1, 0, 1, 2]:
            r = math.hypot(col, row)
            # IL gets worse with radius, FSR slightly varies
            rows.append({
                "Wafer": "D08",
                "Session": "S1",
                "Die": f"({col},{row})",
                "DieCol": col,
                "DieRow": row,
                "FSR_nm": 9.85 + 0.01 * (r - 2),
                "PeakIL_near_1310_dB": -6.5 - 0.6 * r,
                "I_at_-1V_pA": 5e4 + 1e3 * r,
                "dLambda_dV_pm_per_V": -160.0,
                "FailedContact": False,
            })
    return pd.DataFrame(rows)


# ------------------------ uniformity tests ------------------------ #
def test_add_radius_column_computes_distance(sample_features):
    df = add_radius_column(sample_features)
    assert "Radius" in df.columns
    # Die (0,0) has radius 0
    center = df[(df["DieCol"] == 0) & (df["DieRow"] == 0)]
    assert math.isclose(center["Radius"].iloc[0], 0.0)
    # Die (2,2) has radius 2*sqrt(2)
    corner = df[(df["DieCol"] == 2) & (df["DieRow"] == 2)]
    assert math.isclose(corner["Radius"].iloc[0], 2.0 * math.sqrt(2))


def test_add_region_splits_at_threshold(sample_features):
    df = add_region_column(sample_features, edge_radius=1.5)
    centers = df[df["Region"] == "center"]
    edges = df[df["Region"] == "edge"]
    # All center dies have radius <= 1.5
    assert (centers["Radius"] <= 1.5).all()
    assert (edges["Radius"] > 1.5).all()


def test_center_vs_edge_detects_synthetic_gradient(sample_features):
    out = center_vs_edge(sample_features, "PeakIL_near_1310_dB", group_by=["Wafer"])
    assert len(out) == 1
    row = out.iloc[0]
    # Center IL should be greater (less negative) than edge IL
    assert row["center_median"] > row["edge_median"]
    # Delta should be positive
    assert row["delta_center_minus_edge"] > 0


def test_center_vs_edge_raises_for_unknown_metric(sample_features):
    with pytest.raises(KeyError):
        center_vs_edge(sample_features, "NoSuchMetric")


def test_per_radius_stats_returns_one_row_per_radius(sample_features):
    out = per_radius_stats(sample_features, "PeakIL_near_1310_dB", group_by=["Wafer"])
    assert "RadiusBin" in out.columns
    # For our 5x5 grid the rounded radii span 0..3
    assert set(out["RadiusBin"].unique()).issubset({0, 1, 2, 3})


def test_fsr_to_index_variation_reports_relative_pct(sample_features):
    out = fsr_to_index_variation(sample_features, group_by=["Wafer"])
    assert len(out) == 1
    row = out.iloc[0]
    assert row["FSR_relative_variation_pct"] > 0
    assert row["Implied_index_variation_pct"] == row["FSR_relative_variation_pct"]


def test_iv_uniformity_returns_robust_stats(sample_features):
    out = iv_uniformity(sample_features, group_by=["Wafer"])
    assert {"mean", "std", "CV_pct", "median", "mad_std"}.issubset(out.columns)
    row = out.iloc[0]
    assert row["n"] == len(sample_features)


def test_iv_uniformity_handles_empty():
    df = pd.DataFrame(columns=["Wafer", "I_at_-1V_pA"])
    out = iv_uniformity(df, group_by=["Wafer"])
    assert out.empty


# --------------------------- phase tests --------------------------- #
def test_parse_phaseshifter_length_um_finds_first_int():
    assert parse_phaseshifter_length_um("MZMOTE_LULAB_380_500") == 380.0
    assert parse_phaseshifter_length_um("FOO_1234_BAR") == 1234.0


def test_parse_phaseshifter_length_um_returns_nan_when_absent():
    assert math.isnan(parse_phaseshifter_length_um(""))
    assert math.isnan(parse_phaseshifter_length_um("NoNumbersHere"))


def test_voltage_to_phase_zero_at_zero_bias():
    biases = np.array([-1.0, 0.0, 1.0])
    notches = np.array([1310.5, 1310.0, 1309.5])  # linear shift
    fsr = 10.0
    phi = voltage_to_phase(biases, notches, fsr)
    # Phase at 0V (the reference) must be exactly 0
    assert math.isclose(phi[1], 0.0)
    # Symmetric around 0 because of linear shift
    assert math.isclose(phi[0], -phi[2], abs_tol=1e-12)


def test_voltage_to_phase_uses_2pi_per_fsr():
    """One FSR of shift should equal 2π of phase."""
    biases = np.array([0.0, 1.0])
    fsr = 10.0
    notches = np.array([1310.0, 1320.0])  # exactly one FSR shifted
    phi = voltage_to_phase(biases, notches, fsr)
    assert math.isclose(phi[1], 2 * math.pi)


def test_vpi_from_slope_basic():
    # FSR=10 nm, slope=0.5 nm/V → Vπ = 10/(2*0.5) = 10 V
    assert math.isclose(vpi_from_slope(0.5, 10.0), 10.0)
    # Sign of slope shouldn't matter
    assert math.isclose(vpi_from_slope(-0.5, 10.0), 10.0)


def test_vpi_from_slope_returns_nan_for_invalid():
    assert math.isnan(vpi_from_slope(float("nan"), 10.0))
    assert math.isnan(vpi_from_slope(0.5, float("nan")))
    assert math.isnan(vpi_from_slope(0.0, 10.0))
