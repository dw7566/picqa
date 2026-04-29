"""Typed data containers for photonic measurement files.

These dataclasses represent parsed XML measurements in a structured form so
downstream extraction modules don't have to know about XML.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class IVMeasurement:
    """Voltage-current sweep on a device terminal."""

    voltage: np.ndarray  # in volts
    current: np.ndarray  # in amps

    def at(self, target_v: float) -> float:
        """Return the current at the voltage closest to ``target_v``."""
        idx = int(np.argmin(np.abs(self.voltage - target_v)))
        return float(self.current[idx])


@dataclass
class WavelengthSweep:
    """Optical transmission vs wavelength at a fixed DC bias."""

    wavelength_nm: np.ndarray
    insertion_loss_db: np.ndarray
    dc_bias_v: float
    power_dbm: float | None = None

    def il_at(self, wavelength_nm: float) -> float:
        """Linear interpolation of IL at a given wavelength."""
        return float(np.interp(wavelength_nm, self.wavelength_nm, self.insertion_loss_db))


@dataclass
class Measurement:
    """A single device measurement (one die, one test type, one session).

    Attributes
    ----------
    wafer, die_col, die_row, die : die identifiers
    batch, maskset : process identifiers
    test_site : test type tag (e.g. ``DCM_LMZO``)
    device_name : design name (e.g. ``MZMOTE_LULAB_380_500``)
    design_params : ``{symbol: value}`` from XML's ``DesignParameter`` blocks
    design_wavelength_nm : nominal operating wavelength parsed from the XML's
        ``WL`` design parameter, or inferred from the test-site name when
        absent (e.g. ``LMZO`` → 1310 nm O-band, ``LMZC`` → 1550 nm C-band).
        ``None`` if neither source provides one.
    band : derived telecom band label, one of ``"O"``, ``"C"``, ``"L"``,
        ``"S"``, ``"E"``, or ``""`` if undetermined.
    iv : optional IV sweep
    sweeps : list of wavelength sweeps (varying bias)
    align_wavelength_nm : alignment laser wavelength
    creation_date : ISO-like timestamp string from the XML header
    session : session directory name
    source_path : original XML file path
    """

    wafer: str
    die_col: int
    die_row: int
    batch: str = ""
    maskset: str = ""
    test_site: str = ""
    device_name: str = ""
    design_params: dict[str, str] = field(default_factory=dict)
    design_wavelength_nm: float | None = None
    band: str = ""
    iv: IVMeasurement | None = None
    sweeps: list[WavelengthSweep] = field(default_factory=list)
    align_wavelength_nm: float | None = None
    creation_date: str = ""
    session: str = ""
    source_path: str = ""

    @property
    def die(self) -> str:
        """Die label such as ``(0,0)`` or ``(-3,2)``."""
        return f"({self.die_col},{self.die_row})"

    def sweep_at_bias(self, bias_v: float, tol: float = 0.01) -> WavelengthSweep | None:
        """Return the first sweep whose bias is within ``tol`` of ``bias_v``."""
        for sw in self.sweeps:
            if abs(sw.dc_bias_v - bias_v) <= tol:
                return sw
        return None
