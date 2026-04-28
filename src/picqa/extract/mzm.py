"""Extract MZ modulator (DCM_LMZO) characteristics.

Features extracted per die:

* ``FSR_nm`` — free spectral range, median of notch-to-notch spacing at 0V.
* ``Notch_at_0V_nm`` — wavelength of the resonance closest to 1310 nm at 0V.
* ``dLambda_dV_pm_per_V`` — bias-induced shift of that resonance, in pm/V.
* ``PeakIL_near_1310_dB`` — 95th-percentile envelope IL within ±4 nm of 1310 nm
  at 0V (approximates the grating coupler peak).
* ``I_at_-1V_pA``, ``I_at_-2V_pA`` — reverse-bias leakage currents.

Notes
-----
The tuning slope is fit by tracking a single notch across all biases. If the
nearest notch in another sweep is more than half an FSR away, the tracking
is treated as a mismatch and the fit excludes that point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from picqa.io.schemas import Measurement, WavelengthSweep

logger = logging.getLogger(__name__)

DESIGN_WAVELENGTH_NM = 1310.0
NOTCH_PROMINENCE_DB = 8.0
ENVELOPE_WINDOW_NM = 4.0


@dataclass
class MZMFeatures:
    """Feature record for one MZM measurement."""

    wafer: str
    session: str
    die: str
    die_col: int
    die_row: int
    fsr_nm: float
    notch_at_0v_nm: float
    dlambda_dv_pm_per_v: float
    peak_il_near_1310_db: float
    i_at_minus_1v_pa: float
    i_at_minus_2v_pa: float


def _find_notches(
    wavelength_nm: np.ndarray,
    il_db: np.ndarray,
    prominence_db: float = NOTCH_PROMINENCE_DB,
) -> tuple[np.ndarray, np.ndarray]:
    """Return wavelengths and depths of transmission minima.

    Notches are minima in IL[dB], so we run :func:`scipy.signal.find_peaks` on
    the negated trace.
    """
    peaks, _ = find_peaks(-il_db, prominence=prominence_db)
    return wavelength_nm[peaks], il_db[peaks]


def _envelope_il(
    sweep: WavelengthSweep,
    near_lambda: float = DESIGN_WAVELENGTH_NM,
    window_nm: float = ENVELOPE_WINDOW_NM,
) -> float:
    """95th-percentile IL inside a wavelength window.

    Returns ``nan`` if the window contains no samples.
    """
    mask = (sweep.wavelength_nm >= near_lambda - window_nm) & (
        sweep.wavelength_nm <= near_lambda + window_nm
    )
    if not mask.any():
        return float("nan")
    return float(np.percentile(sweep.insertion_loss_db[mask], 95))


def _tune_slope_pm_per_v(
    sweeps: list[WavelengthSweep],
    fsr_nm: float,
    seed_lambda_nm: float,
) -> float:
    """Linear fit of tracked notch wavelength vs DC bias (returns slope in pm/V)."""
    if len(sweeps) < 3:
        return float("nan")

    bias_list: list[float] = []
    lam_list: list[float] = []
    ref_lam = seed_lambda_nm
    half_fsr = fsr_nm / 2.0 if not np.isnan(fsr_nm) else 5.0

    for s in sorted(sweeps, key=lambda x: x.dc_bias_v):
        nl, _ = _find_notches(s.wavelength_nm, s.insertion_loss_db)
        if nl.size == 0:
            continue
        j = int(np.argmin(np.abs(nl - ref_lam)))
        if abs(nl[j] - ref_lam) > half_fsr:
            continue  # tracking lost
        bias_list.append(s.dc_bias_v)
        lam_list.append(float(nl[j]))
        ref_lam = float(nl[j])

    if len(bias_list) < 3:
        return float("nan")

    slope_nm_per_v, _ = np.polyfit(bias_list, lam_list, 1)
    return float(slope_nm_per_v * 1000.0)  # nm/V → pm/V


def extract_one(m: Measurement) -> MZMFeatures | None:
    """Extract features from a single MZM measurement.

    Returns ``None`` if the measurement lacks the data needed (no 0V sweep).
    """
    sweep0 = m.sweep_at_bias(0.0)
    if sweep0 is None:
        return None

    notches, _ = _find_notches(sweep0.wavelength_nm, sweep0.insertion_loss_db)

    if notches.size >= 2:
        fsr = float(np.median(np.diff(notches)))
    else:
        fsr = float("nan")

    if notches.size > 0:
        ref_idx = int(np.argmin(np.abs(notches - DESIGN_WAVELENGTH_NM)))
        notch_at_0v = float(notches[ref_idx])
        slope = _tune_slope_pm_per_v(m.sweeps, fsr, notch_at_0v)
    else:
        notch_at_0v = float("nan")
        slope = float("nan")

    peak_il = _envelope_il(sweep0)

    if m.iv is not None:
        i_m1 = m.iv.at(-1.0) * 1e12  # A → pA
        i_m2 = m.iv.at(-2.0) * 1e12
    else:
        i_m1 = float("nan")
        i_m2 = float("nan")

    return MZMFeatures(
        wafer=m.wafer,
        session=m.session,
        die=m.die,
        die_col=m.die_col,
        die_row=m.die_row,
        fsr_nm=fsr,
        notch_at_0v_nm=notch_at_0v,
        dlambda_dv_pm_per_v=slope,
        peak_il_near_1310_db=peak_il,
        i_at_minus_1v_pa=i_m1,
        i_at_minus_2v_pa=i_m2,
    )


def extract_mzm_features(measurements: list[Measurement]) -> pd.DataFrame:
    """Extract MZM features from many measurements.

    Only ``test_site == 'DCM_LMZO'`` measurements are processed. Returns an
    empty DataFrame with the expected columns if no input matches.
    """
    rows: list[dict] = []
    for m in measurements:
        if m.test_site != "DCM_LMZO":
            continue
        feat = extract_one(m)
        if feat is None:
            continue
        rows.append(
            {
                "Wafer": feat.wafer,
                "Session": feat.session,
                "Die": feat.die,
                "DieCol": feat.die_col,
                "DieRow": feat.die_row,
                "FSR_nm": feat.fsr_nm,
                "Notch_at_0V_nm": feat.notch_at_0v_nm,
                "dLambda_dV_pm_per_V": feat.dlambda_dv_pm_per_v,
                "PeakIL_near_1310_dB": feat.peak_il_near_1310_db,
                "I_at_-1V_pA": feat.i_at_minus_1v_pa,
                "I_at_-2V_pA": feat.i_at_minus_2v_pa,
            }
        )

    columns = [
        "Wafer", "Session", "Die", "DieCol", "DieRow",
        "FSR_nm", "Notch_at_0V_nm", "dLambda_dV_pm_per_V",
        "PeakIL_near_1310_dB", "I_at_-1V_pA", "I_at_-2V_pA",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)
