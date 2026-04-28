"""XML parser for photonic test measurement files.

Files share a common ``OIOMeasurement`` root and embed measurement data inside
``OpticalMeasurements`` or ``ElectroOpticalMeasurements`` subtrees. Different
test types (``DCM_LMZO``, ``DCM_GPDO``, ``OTEST_L3OTE``...) put data in
slightly different containers, so this module handles them uniformly.
"""

from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from picqa.io.schemas import IVMeasurement, Measurement, WavelengthSweep

logger = logging.getLogger(__name__)

# Top-level wrapper tags whose first non-alignment Modulator/Loss block we want
_WRAPPER_TAGS = {"Modulator", "WaveguideLossMeasurement", "DetectorMeasurement"}


def _localname(tag: str) -> str:
    """Strip XML namespace if present."""
    return tag.split("}", 1)[-1]


def _to_array(text: str | None) -> np.ndarray:
    """Parse a comma-separated number string into a numpy array."""
    if text is None:
        return np.array([], dtype=float)
    return np.fromstring(text.strip(), sep=",")


def _parse_iv(elem: ET.Element) -> IVMeasurement | None:
    iv = elem.find(".//IVMeasurement")
    if iv is None:
        return None
    v_el = iv.find("Voltage")
    i_el = iv.find("Current")
    if v_el is None or i_el is None:
        return None
    v = _to_array(v_el.text)
    i = _to_array(i_el.text)
    if v.size == 0 or i.size == 0 or v.size != i.size:
        return None
    return IVMeasurement(voltage=v, current=i)


def _parse_sweeps(elem: ET.Element) -> list[WavelengthSweep]:
    sweeps: list[WavelengthSweep] = []
    for ws in elem.findall(".//WavelengthSweep"):
        l_el = ws.find("L")
        il_el = ws.find("IL")
        if l_el is None or il_el is None:
            continue
        L = _to_array(l_el.text)
        IL = _to_array(il_el.text)
        if L.size == 0 or IL.size == 0 or L.size != IL.size:
            continue
        try:
            bias = float(ws.attrib.get("DCBias", "nan"))
        except ValueError:
            bias = float("nan")
        try:
            power = float(ws.attrib.get("Power", "nan"))
        except ValueError:
            power = None
        sweeps.append(
            WavelengthSweep(
                wavelength_nm=L,
                insertion_loss_db=IL,
                dc_bias_v=bias,
                power_dbm=power if power is not None and not np.isnan(power) else None,
            )
        )
    return sweeps


def _find_main_block(root: ET.Element) -> ET.Element | None:
    """Return the first measurement block that is not an alignment reference."""
    candidates: list[ET.Element] = []
    for elem in root.iter():
        if _localname(elem.tag) in _WRAPPER_TAGS:
            candidates.append(elem)
    if not candidates:
        return None
    # Prefer a non-alignment block
    for c in candidates:
        name = c.attrib.get("Name", "")
        if "ALIGN" not in name.upper():
            return c
    return candidates[0]


def _parse_design_params(elem: ET.Element) -> dict[str, str]:
    params: dict[str, str] = {}
    for dp in elem.iter():
        if _localname(dp.tag) == "DesignParameter":
            symbol = dp.attrib.get("Symbol", "")
            if symbol and dp.text:
                params[symbol] = dp.text.strip()
    return params


# Regex for extracting test site tag from filename, e.g. ``..._LION1_DCM_LMZO.xml``
_TESTSITE_RE = re.compile(r"_LION1_(.+?)\.xml$")


def parse_measurement(path: str | os.PathLike) -> Measurement | None:
    """Parse a single XML file into a :class:`Measurement`.

    Returns ``None`` on parse failure. Logs the cause at WARNING level.
    """
    p = Path(path)
    if not p.is_file():
        logger.warning("File not found: %s", p)
        return None
    try:
        tree = ET.parse(p)
    except ET.ParseError as exc:
        logger.warning("XML parse error in %s: %s", p, exc)
        return None

    root = tree.getroot()
    ts = root.find("TestSiteInfo")
    info = dict(ts.attrib) if ts is not None else {}

    # Test site: take from XML if present, else from filename
    test_site = info.get("TestSite", "")
    if not test_site:
        m = _TESTSITE_RE.search(p.name)
        if m:
            test_site = m.group(1)

    main = _find_main_block(root)
    device_name = main.attrib.get("Name", "") if main is not None else ""

    # Parse IV and sweeps only from inside the main measurement block so we
    # don't pick up alignment-only WavelengthSweeps that some test sites
    # include in a separate ``ALIGN`` ``Modulator`` element.
    parse_root = main if main is not None else root
    iv = _parse_iv(parse_root)
    sweeps = _parse_sweeps(parse_root)
    design_params = _parse_design_params(main) if main is not None else {}

    align = root.find(".//AlignWavelength")
    align_wl: float | None = None
    if align is not None and align.text:
        try:
            align_wl = float(align.text.strip())
        except ValueError:
            align_wl = None

    try:
        die_col = int(info.get("DieColumn", 0))
        die_row = int(info.get("DieRow", 0))
    except ValueError:
        logger.warning("Invalid die coordinate in %s", p)
        return None

    return Measurement(
        wafer=info.get("Wafer", ""),
        die_col=die_col,
        die_row=die_row,
        batch=info.get("Batch", ""),
        maskset=info.get("Maskset", ""),
        test_site=test_site,
        device_name=device_name,
        design_params=design_params,
        iv=iv,
        sweeps=sweeps,
        align_wavelength_nm=align_wl,
        creation_date=root.attrib.get("CreationDate", ""),
        session=p.parent.name,
        source_path=str(p),
    )


def parse_directory(
    data_dir: str | os.PathLike,
    test_site: str | None = None,
) -> list[Measurement]:
    """Parse every XML under ``data_dir``, optionally filtering by test site.

    Parameters
    ----------
    data_dir : str | Path
        Root directory containing wafer subfolders (e.g. ``D08``, ``D24``).
    test_site : str | None
        If given, only files whose test site matches (case-sensitive) are
        included (e.g. ``"DCM_LMZO"``).
    """
    root_path = Path(data_dir)
    if not root_path.is_dir():
        raise FileNotFoundError(f"Data directory not found: {root_path}")

    pattern = "**/*.xml"
    if test_site:
        pattern = f"**/*_LION1_{test_site}.xml"

    measurements: list[Measurement] = []
    for f in sorted(root_path.glob(pattern)):
        m = parse_measurement(f)
        if m is None:
            continue
        if test_site and m.test_site != test_site:
            continue
        measurements.append(m)

    logger.info(
        "Parsed %d measurements from %s (test_site=%s)",
        len(measurements),
        root_path,
        test_site,
    )
    return measurements


def inventory(data_dir: str | os.PathLike) -> dict:
    """Return a quick inventory of files under ``data_dir`` (no full parse)."""
    root_path = Path(data_dir)
    if not root_path.is_dir():
        raise FileNotFoundError(f"Data directory not found: {root_path}")

    by_wafer: dict[str, int] = {}
    by_test: dict[str, int] = {}
    total_size = 0
    n_files = 0

    for f in root_path.rglob("*.xml"):
        n_files += 1
        total_size += f.stat().st_size
        # wafer = top-level folder under data_dir
        try:
            wafer = f.relative_to(root_path).parts[0]
            by_wafer[wafer] = by_wafer.get(wafer, 0) + 1
        except IndexError:
            pass
        m = _TESTSITE_RE.search(f.name)
        if m:
            by_test[m.group(1)] = by_test.get(m.group(1), 0) + 1

    return {
        "n_files": n_files,
        "total_size_bytes": total_size,
        "by_wafer": dict(sorted(by_wafer.items())),
        "by_test_site": dict(sorted(by_test.items(), key=lambda x: -x[1])),
    }
