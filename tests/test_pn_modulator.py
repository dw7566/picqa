"""Tests for PN modulator parsing and feature extraction."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from picqa.extract.pn_modulator import (
    extract_pn_length_fit,
    extract_pn_segment_features,
)
from picqa.io.pn_parser import parse_pn_directory, parse_pn_measurement


SAMPLE_PN = Path(__file__).parent / "data" / "sample_pn.xml"


@pytest.fixture
def sample_pn_measurement():
    m = parse_pn_measurement(SAMPLE_PN)
    assert m is not None
    return m


def test_parse_pn_basic(sample_pn_measurement):
    m = sample_pn_measurement
    assert m.wafer == "D24"
    assert m.die == "(0,0)"
    assert m.test_site == "PCM_PSLOTE_P1N1"


def test_parse_pn_lengths(sample_pn_measurement):
    assert sample_pn_measurement.design_lengths_um == [500.0, 1500.0, 2500.0]


def test_parse_pn_has_reference_and_three_segments(sample_pn_measurement):
    assert sample_pn_measurement.reference is not None
    assert sample_pn_measurement.reference.is_reference is True
    actives = sample_pn_measurement.active_segments
    assert len(actives) == 3
    assert [s.length_um for s in actives] == [500.0, 1500.0, 2500.0]


def test_pn_active_segments_have_iv_and_six_sweeps(sample_pn_measurement):
    for seg in sample_pn_measurement.active_segments:
        assert seg.iv is not None
        assert seg.iv.voltage.size > 0
        biases = sorted(s.dc_bias_v for s in seg.sweeps)
        assert biases == [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5]


def test_pn_reference_has_no_iv(sample_pn_measurement):
    ref = sample_pn_measurement.reference
    assert ref.iv is None
    # Reference has only a 0V sweep
    assert len(ref.sweeps) == 1
    assert ref.sweeps[0].dc_bias_v == 0.0


def test_extract_segment_features_dataframe(sample_pn_measurement):
    df = extract_pn_segment_features([sample_pn_measurement])
    assert len(df) == 3
    expected_cols = {
        "Wafer", "Session", "Die", "Length_um",
        "PeakIL_at_1310_dB", "IL_drop_vs_REF_dB",
        "dIL_dV_dB_per_V", "I_at_-1V_pA", "I_at_-2V_pA",
    }
    assert expected_cols.issubset(set(df.columns))
    # IL drop should be monotonically more negative with longer segments
    df_sorted = df.sort_values("Length_um")
    drops = df_sorted["IL_drop_vs_REF_dB"].values
    assert drops[0] > drops[1] > drops[2]  # more negative as length grows


def test_extract_length_fit_returns_one_row_per_die(sample_pn_measurement):
    seg_df = extract_pn_segment_features([sample_pn_measurement])
    fit = extract_pn_length_fit(seg_df)
    assert len(fit) == 1
    row = fit.iloc[0]
    assert row["n_lengths"] == 3
    # Loss slope should be negative (loss grows with length)
    assert row["Loss_per_um_dB_per_um"] < 0
    # R² should be high since the points are colinear-ish
    assert row["Loss_R2"] > 0.9


def test_modulation_slope_finite_for_working_die(sample_pn_measurement):
    df = extract_pn_segment_features([sample_pn_measurement])
    # All three slopes should be finite numbers (not NaN) for this working die
    for v in df["dIL_dV_dB_per_V"]:
        assert math.isfinite(v)


def test_extract_empty_input_returns_typed_empty():
    df = extract_pn_segment_features([])
    assert df.empty
    assert "Length_um" in df.columns
    fit = extract_pn_length_fit(df)
    assert fit.empty
    assert "Loss_per_um_dB_per_um" in fit.columns


def test_parse_pn_directory_finds_file(tmp_path):
    # Build a minimal directory tree
    target = tmp_path / "D24" / "20190603_225101"
    target.mkdir(parents=True)
    import shutil
    shutil.copy(SAMPLE_PN,
                target / "HY202103_D24_(0,0)_LION1_PCM_PSLOTE_P1N1.xml")

    out = parse_pn_directory(tmp_path)
    assert len(out) == 1
    assert out[0].wafer == "D24"
