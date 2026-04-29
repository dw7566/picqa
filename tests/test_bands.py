"""Tests for telecom-band utilities and design-wavelength parsing."""

from __future__ import annotations

import math

from picqa.io.bands import (
    band_for_measurement,
    band_from_name,
    band_from_wavelength,
    default_wavelength_for_band,
)


# ------------------------- band_from_wavelength ------------------------- #
def test_band_from_wavelength_o_band():
    assert band_from_wavelength(1310.0) == "O"
    assert band_from_wavelength(1260.0) == "O"
    assert band_from_wavelength(1359.0) == "O"


def test_band_from_wavelength_c_band():
    assert band_from_wavelength(1530.0) == "C"
    assert band_from_wavelength(1550.0) == "C"
    assert band_from_wavelength(1564.99) == "C"


def test_band_from_wavelength_l_band():
    assert band_from_wavelength(1565.0) == "L"
    assert band_from_wavelength(1600.0) == "L"


def test_band_from_wavelength_below_o():
    assert band_from_wavelength(1200.0) == ""


def test_band_from_wavelength_handles_none_and_invalid():
    assert band_from_wavelength(None) == ""
    assert band_from_wavelength("not a number") == ""


# ------------------------- band_from_name ------------------------- #
def test_band_from_name_recognises_lmzo():
    assert band_from_name("DCM_LMZO") == "O"
    assert band_from_name("dcm_lmzc") == "C"


def test_band_from_name_recognises_mzm():
    assert band_from_name("MZMOTE_LULAB_380_500") == "O"
    assert band_from_name("MZMCTE_LULAB_450_500") == "C"


def test_band_from_name_recognises_psl():
    assert band_from_name("PCM_PSLOTE_P1N1") == "O"
    assert band_from_name("PCM_PSLCTE_P1N1") == "C"


def test_band_from_name_returns_empty_for_unrelated():
    # ALIGN_WAFER_CTE has 'CTE' but no LMZ/MZM/PSL prefix → must not match
    assert band_from_name("ALIGN_WAFER_CTE") == ""
    assert band_from_name("DCM_GPDO") == ""
    assert band_from_name("") == ""


# ------------------------- band_for_measurement ------------------------- #
def test_band_for_measurement_prefers_explicit_wavelength():
    # Explicit wavelength wins even if name says otherwise
    band = band_for_measurement(
        design_wavelength_nm=1550.0,
        test_site="DCM_LMZO",   # would map to O
        device_name="MZMOTE_X",  # would map to O
    )
    assert band == "C"


def test_band_for_measurement_falls_back_to_test_site():
    band = band_for_measurement(
        design_wavelength_nm=None,
        test_site="DCM_LMZC",
        device_name="",
    )
    assert band == "C"


def test_band_for_measurement_falls_back_to_device_name():
    band = band_for_measurement(
        design_wavelength_nm=None,
        test_site="UNKNOWN_TEST",
        device_name="MZMCTE_LULAB_450_500",
    )
    assert band == "C"


def test_band_for_measurement_returns_empty_when_nothing_matches():
    band = band_for_measurement(
        design_wavelength_nm=None,
        test_site="UNKNOWN",
        device_name="UNKNOWN",
    )
    assert band == ""


# ------------------------- default_wavelength_for_band ------------------------- #
def test_default_wavelength_for_band():
    assert default_wavelength_for_band("O") == 1310.0
    assert default_wavelength_for_band("C") == 1550.0
    assert default_wavelength_for_band("L") == 1590.0
    assert default_wavelength_for_band("Z") is None
    assert default_wavelength_for_band("") is None
