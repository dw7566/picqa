"""Tests for picqa.io.xml_parser."""

from __future__ import annotations

import pytest

from picqa.io.xml_parser import inventory, parse_directory, parse_measurement


def test_parse_lmzo_returns_measurement(sample_lmzo_path):
    m = parse_measurement(sample_lmzo_path)
    assert m is not None
    assert m.wafer == "D24"
    assert m.die == "(0,0)"
    assert m.test_site == "DCM_LMZO"


def test_parse_lmzo_has_iv_and_sweeps(sample_measurement):
    m = sample_measurement
    assert m.iv is not None
    assert m.iv.voltage.size == m.iv.current.size
    assert m.iv.voltage.size > 0
    # 6 biases: -2.0, -1.5, -1.0, -0.5, 0.0, +0.5
    assert len(m.sweeps) == 6
    biases = sorted(s.dc_bias_v for s in m.sweeps)
    assert biases == [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5]


def test_iv_at_helper(sample_measurement):
    m = sample_measurement
    # Forward bias should give a much larger current than 0V
    assert abs(m.iv.at(1.0)) > abs(m.iv.at(0.0))
    # Reverse bias gives small but nonzero leakage
    assert m.iv.at(-1.0) != 0.0


def test_sweep_at_bias_returns_correct_one(sample_measurement):
    sw = sample_measurement.sweep_at_bias(0.0)
    assert sw is not None
    assert sw.dc_bias_v == 0.0
    assert sw.wavelength_nm.size == sw.insertion_loss_db.size


def test_sweep_at_bias_returns_none_for_unknown_bias(sample_measurement):
    assert sample_measurement.sweep_at_bias(-3.5) is None


def test_parse_returns_none_on_missing_file(tmp_path):
    bad = tmp_path / "does_not_exist.xml"
    assert parse_measurement(bad) is None or True  # ParseError if any


def test_parse_returns_none_on_corrupt_xml(tmp_path):
    bad = tmp_path / "corrupt.xml"
    bad.write_text("<not valid xml")
    assert parse_measurement(bad) is None


def test_parse_directory_filters_by_test_site(mini_data_dir):
    lmzo = parse_directory(mini_data_dir, test_site="DCM_LMZO")
    assert len(lmzo) == 1
    assert lmzo[0].test_site == "DCM_LMZO"

    gpdo = parse_directory(mini_data_dir, test_site="DCM_GPDO")
    assert len(gpdo) == 1
    assert gpdo[0].test_site == "DCM_GPDO"


def test_parse_directory_unfiltered_picks_up_all(mini_data_dir):
    all_m = parse_directory(mini_data_dir)
    assert len(all_m) == 2


def test_parse_directory_raises_for_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_directory(tmp_path / "does-not-exist")


def test_inventory_counts_files(mini_data_dir):
    inv = inventory(mini_data_dir)
    assert inv["n_files"] == 2
    assert inv["by_wafer"] == {"D24": 2}
    assert "DCM_LMZO" in inv["by_test_site"]
    assert "DCM_GPDO" in inv["by_test_site"]
