"""Tests for picqa.extract.mzm."""

from __future__ import annotations

import math

import numpy as np

from picqa.extract.mzm import (
    DESIGN_WAVELENGTH_NM,
    extract_mzm_features,
    extract_one,
)


def test_extract_one_returns_features(sample_measurement):
    feat = extract_one(sample_measurement)
    assert feat is not None
    # Sanity ranges based on the dataset's known characteristics
    assert 9.0 < feat.fsr_nm < 11.0
    assert 1300.0 < feat.notch_at_0v_nm < 1320.0
    assert -50.0 < feat.peak_il_near_1310_db < 0.0
    # I/V leakage at -1V should be in the pA-to-nA range (failed contact at this die),
    # so just check it's finite.
    assert math.isfinite(feat.i_at_minus_1v_pa)


def test_design_wavelength_constant():
    assert DESIGN_WAVELENGTH_NM == 1310.0


def test_extract_mzm_features_dataframe_columns(sample_measurement):
    df = extract_mzm_features([sample_measurement])
    expected = {
        "Wafer", "Session", "Die", "DieCol", "DieRow",
        "FSR_nm", "Notch_at_0V_nm", "dLambda_dV_pm_per_V",
        "PeakIL_near_1310_dB", "I_at_-1V_pA", "I_at_-2V_pA",
    }
    assert expected.issubset(set(df.columns))
    assert len(df) == 1


def test_extract_mzm_features_skips_other_test_sites(sample_measurement):
    # Force a mock measurement of a different test site
    other = sample_measurement
    other.test_site = "DCM_GPDO"
    df = extract_mzm_features([other])
    assert df.empty


def test_extract_mzm_features_empty_input_returns_typed_empty():
    df = extract_mzm_features([])
    assert df.empty
    assert "FSR_nm" in df.columns


def test_extract_one_returns_none_without_zero_bias_sweep(sample_measurement):
    # Drop the 0V sweep
    m = sample_measurement
    m.sweeps = [s for s in m.sweeps if s.dc_bias_v != 0.0]
    assert extract_one(m) is None
