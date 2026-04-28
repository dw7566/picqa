"""Parser for PN modulator (PCM_PSLOTE_P1N1) XML files.

These files contain one ``ModulatorSite`` with a ``Modulator`` block holding:

* A ``DeviceInfo`` with a ``DesignParameter`` named ``Lengths`` (a Python-style
  list, e.g. ``[500, 1500, 2500]``) giving the active lengths in µm.
* Several ``PortCombo`` blocks, one per measurement port pair. The first one
  is typically a reference (bare waveguide, only an optical sweep at 0V), and
  the others correspond, in order, to PN segments of the design lengths.
"""

from __future__ import annotations

import ast
import logging
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from picqa.io.pn_schemas import PNMeasurement, PNSegment
from picqa.io.schemas import IVMeasurement, WavelengthSweep
from picqa.io.xml_parser import _localname, _to_array

logger = logging.getLogger(__name__)


def _parse_lengths(text: str | None) -> list[float]:
    """Parse ``Lengths`` text such as ``"[500, 1500, 2500]"`` into a list."""
    if not text:
        return []
    try:
        val = ast.literal_eval(text.strip())
        if isinstance(val, (list, tuple)):
            return [float(x) for x in val]
        return [float(val)]
    except (ValueError, SyntaxError):
        # Fallback: extract any floats by regex
        return [float(x) for x in re.findall(r"-?\d+\.?\d*", text)]


def _parse_iv_block(elem: ET.Element) -> IVMeasurement | None:
    v_el = elem.find("Voltage")
    i_el = elem.find("Current")
    if v_el is None or i_el is None:
        return None
    v = _to_array(v_el.text)
    i = _to_array(i_el.text)
    if v.size == 0 or i.size == 0 or v.size != i.size:
        return None
    return IVMeasurement(voltage=v, current=i)


def _parse_sweep_block(elem: ET.Element) -> WavelengthSweep | None:
    l_el = elem.find("L")
    il_el = elem.find("IL")
    if l_el is None or il_el is None:
        return None
    L = _to_array(l_el.text)
    IL = _to_array(il_el.text)
    if L.size == 0 or IL.size == 0 or L.size != IL.size:
        return None
    try:
        bias = float(elem.attrib.get("DCBias", "nan"))
    except ValueError:
        bias = float("nan")
    try:
        power = float(elem.attrib.get("Power", "nan"))
        if np.isnan(power):
            power = None
    except ValueError:
        power = None
    return WavelengthSweep(
        wavelength_nm=L,
        insertion_loss_db=IL,
        dc_bias_v=bias,
        power_dbm=power,
    )


def _parse_port_combo(pc: ET.Element) -> PNSegment:
    left = pc.attrib.get("Left", "")
    right = pc.attrib.get("Right", "")
    label = f"{left}/{right}" if (left or right) else pc.attrib.get("Probe", "?")
    is_ref = ("REF" in left.upper()) or ("REF" in right.upper())

    iv: IVMeasurement | None = None
    sweeps: list[WavelengthSweep] = []
    for child in pc:
        ct = _localname(child.tag)
        if ct == "IVMeasurement":
            iv = _parse_iv_block(child)
        elif ct == "WavelengthSweep":
            sw = _parse_sweep_block(child)
            if sw is not None:
                sweeps.append(sw)

    return PNSegment(
        port_label=label,
        is_reference=is_ref,
        iv=iv,
        sweeps=sweeps,
        # length filled in by the caller once the order is known
    )


def parse_pn_measurement(path: str | os.PathLike) -> PNMeasurement | None:
    """Parse a single ``PCM_PSLOTE_P1N1`` XML file.

    Returns ``None`` on parse failure.
    """
    p = Path(path)
    try:
        tree = ET.parse(p)
    except ET.ParseError as exc:
        logger.warning("XML parse error in %s: %s", p, exc)
        return None

    root = tree.getroot()
    ts = root.find("TestSiteInfo")
    info = dict(ts.attrib) if ts is not None else {}

    # Find the Modulator block
    mod = None
    for elem in root.iter():
        if _localname(elem.tag) == "Modulator":
            mod = elem
            break
    if mod is None:
        logger.warning("No <Modulator> in %s", p)
        return None

    # Extract design Lengths
    lengths: list[float] = []
    for dp in mod.iter():
        if _localname(dp.tag) == "DesignParameter" and dp.attrib.get("Symbol") == "L":
            lengths = _parse_lengths(dp.text)
            break

    # Parse all PortCombo children
    segments: list[PNSegment] = []
    for child in mod:
        if _localname(child.tag) == "PortCombo":
            seg = _parse_port_combo(child)
            segments.append(seg)

    # Assign lengths: reference gets None, active segments get lengths in order
    active = [s for s in segments if not s.is_reference]
    for seg, length in zip(active, lengths):
        seg.length_um = length

    try:
        die_col = int(info.get("DieColumn", 0))
        die_row = int(info.get("DieRow", 0))
    except ValueError:
        return None

    return PNMeasurement(
        wafer=info.get("Wafer", ""),
        die_col=die_col,
        die_row=die_row,
        test_site=info.get("TestSite", "PCM_PSLOTE_P1N1"),
        device_name=mod.attrib.get("Name", ""),
        design_lengths_um=lengths,
        segments=segments,
        creation_date=root.attrib.get("CreationDate", ""),
        session=p.parent.name,
        source_path=str(p),
    )


def parse_pn_directory(data_dir: str | os.PathLike) -> list[PNMeasurement]:
    """Parse every ``PCM_PSLOTE_P1N1`` XML under ``data_dir``."""
    root_path = Path(data_dir)
    if not root_path.is_dir():
        raise FileNotFoundError(f"Data directory not found: {root_path}")

    measurements: list[PNMeasurement] = []
    for f in sorted(root_path.glob("**/*_LION1_PCM_PSLOTE_P1N1.xml")):
        m = parse_pn_measurement(f)
        if m is not None:
            measurements.append(m)
    logger.info("Parsed %d PN measurements", len(measurements))
    return measurements
