"""Typed containers for PN modulator (PCM_PSLOTE_P1N1) measurements.

These XML files have a different structure from DCM_LMZO: a ``ModulatorSite``
contains a ``Modulator`` block with multiple ``PortCombo`` children, each
representing one PN segment (or a reference waveguide).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from picqa.io.schemas import IVMeasurement, WavelengthSweep


@dataclass
class PNSegment:
    """One PN modulator segment of a known active length.

    Attributes
    ----------
    port_label : str
        Combined "Left/Right" port identifier from the XML (e.g. ``IN_1/OUT_1``).
    is_reference : bool
        True for the bare-waveguide reference port (no PN doping, no IV).
    length_um : float | None
        Active length of this segment in micrometres. ``None`` for the reference.
    iv : IVMeasurement | None
        Forward/reverse sweep across the PN diode. ``None`` for the reference.
    sweeps : list[WavelengthSweep]
        Optical transmission sweeps at one or more DC biases.
    """

    port_label: str
    is_reference: bool = False
    length_um: float | None = None
    iv: IVMeasurement | None = None
    sweeps: list[WavelengthSweep] = field(default_factory=list)

    def sweep_at_bias(self, bias_v: float, tol: float = 0.01) -> WavelengthSweep | None:
        for sw in self.sweeps:
            if abs(sw.dc_bias_v - bias_v) <= tol:
                return sw
        return None


@dataclass
class PNMeasurement:
    """A complete PN modulator measurement (one die, one session).

    Holds all segments, plus die-level metadata mirrored from
    :class:`~picqa.io.schemas.Measurement`. ``segments`` is ordered so the
    reference (if present) comes first.
    """

    wafer: str
    die_col: int
    die_row: int
    test_site: str = "PCM_PSLOTE_P1N1"
    device_name: str = ""
    design_lengths_um: list[float] = field(default_factory=list)
    segments: list[PNSegment] = field(default_factory=list)
    creation_date: str = ""
    session: str = ""
    source_path: str = ""

    @property
    def die(self) -> str:
        return f"({self.die_col},{self.die_row})"

    @property
    def reference(self) -> PNSegment | None:
        for s in self.segments:
            if s.is_reference:
                return s
        return None

    @property
    def active_segments(self) -> list[PNSegment]:
        return [s for s in self.segments if not s.is_reference and s.length_um is not None]
