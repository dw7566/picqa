"""Shared pytest fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from picqa.io.xml_parser import parse_measurement


DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def sample_lmzo_path() -> Path:
    return DATA_DIR / "sample_lmzo.xml"


@pytest.fixture
def sample_gpdo_path() -> Path:
    return DATA_DIR / "sample_gpdo.xml"


@pytest.fixture
def sample_measurement(sample_lmzo_path):
    """A parsed :class:`Measurement` for a real LMZO file."""
    m = parse_measurement(sample_lmzo_path)
    assert m is not None
    return m


@pytest.fixture
def mini_data_dir(tmp_path: Path, sample_lmzo_path: Path, sample_gpdo_path: Path) -> Path:
    """Construct a small wafer/session tree under a temp dir.

    Layout::

        <tmp>/
          D24/
            20190531_151815/
              HY202103_D24_(0,0)_LION1_DCM_LMZO.xml
              HY202103_D24_(0,0)_LION1_DCM_GPDO.xml
    """
    session_dir = tmp_path / "D24" / "20190531_151815"
    session_dir.mkdir(parents=True)
    shutil.copy(sample_lmzo_path,
                session_dir / "HY202103_D24_(0,0)_LION1_DCM_LMZO.xml")
    shutil.copy(sample_gpdo_path,
                session_dir / "HY202103_D24_(0,0)_LION1_DCM_GPDO.xml")
    return tmp_path
