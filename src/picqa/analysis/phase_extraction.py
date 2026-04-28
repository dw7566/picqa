"""Voltage-phase characterisation of MZ modulators (Project 2).

The bias-dependent wavelength shift of an MZ modulator's transmission notch
maps directly onto an electro-optic phase shift of the active arm. This
module converts the raw ``dλ/dV`` already extracted by the MZM extractor
into the standard performance metrics:

* **Δφ(V)** — phase shift introduced by bias V relative to 0V
* **Vπ** — voltage that yields a π phase shift (one transmission half-period)
* **ER** — extinction ratio between transmission peak and notch
* **Vπ·L** — figure of merit (when phase-shifter length is known)

Key relationship
----------------
A notch in the MZ transmission corresponds to destructive interference, i.e.
a π phase difference between arms. Adjacent notches are spaced by one FSR
(in wavelength). Therefore::

    notch shift Δλ corresponds to phase shift Δφ = 2π · Δλ / FSR
    Vπ = FSR / (2 · |dλ/dV|)

Vπ·L requires the phase-shifter active length, which is not always present
in the XML. We attempt to parse it from the device name (e.g.
``MZMOTE_LULAB_380_500`` → 380 µm) and fall back to NaN when unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from picqa.io.schemas import Measurement, WavelengthSweep


# Regex to grab the first integer that looks like a length from device name
_LENGTH_RE = re.compile(r"_(\d{2,4})_")


def parse_phaseshifter_length_um(device_name: str) -> float:
    """Best-effort parse of a phase-shifter length from a device name.

    For the LION1 PDK an MZM device name like ``MZMOTE_LULAB_380_500`` is
    interpreted as length=380 µm, separation=500 nm. This returns the first
    such integer and is intentionally conservative — callers should treat
    NaN as "unknown".
    """
    if not device_name:
        return float("nan")
    m = _LENGTH_RE.search(device_name)
    if m is None:
        return float("nan")
    try:
        return float(m.group(1))
    except ValueError:
        return float("nan")


def voltage_to_phase(
    biases_v: np.ndarray,
    notch_lambdas_nm: np.ndarray,
    fsr_nm: float,
) -> np.ndarray:
    """Convert tracked notch wavelengths to relative phase shift in radians.

    Phase is defined relative to the entry whose bias is closest to 0 V.
    """
    if biases_v.size == 0 or fsr_nm <= 0 or np.isnan(fsr_nm):
        return np.full_like(biases_v, np.nan, dtype=float)
    ref_idx = int(np.argmin(np.abs(biases_v)))
    delta_lambda = notch_lambdas_nm - notch_lambdas_nm[ref_idx]
    return 2.0 * np.pi * delta_lambda / fsr_nm


def vpi_from_slope(dlambda_dv_nm_per_v: float, fsr_nm: float) -> float:
    """Vπ in volts from tuning slope (nm/V) and FSR (nm).

    Returns NaN if either input is NaN or zero.
    """
    if (
        not np.isfinite(dlambda_dv_nm_per_v)
        or not np.isfinite(fsr_nm)
        or dlambda_dv_nm_per_v == 0
    ):
        return float("nan")
    return float(fsr_nm / (2.0 * abs(dlambda_dv_nm_per_v)))


def extinction_ratio_db(sweep: WavelengthSweep,
                       near_lambda_nm: float = 1310.0,
                       window_nm: float = 5.0) -> float:
    """Extinction ratio at one bias, computed near a target wavelength.

    Defined as (peak IL) − (deepest notch) inside a ±window around
    ``near_lambda_nm``. A higher (more positive) number means a deeper notch
    relative to the spectral envelope.
    """
    L = sweep.wavelength_nm
    IL = sweep.insertion_loss_db
    mask = (L >= near_lambda_nm - window_nm) & (L <= near_lambda_nm + window_nm)
    if not mask.any():
        return float("nan")
    sub = IL[mask]
    return float(sub.max() - sub.min())


# --------------------------------------------------------------------- #
# Per-die feature extraction
# --------------------------------------------------------------------- #
@dataclass
class PhaseFeatures:
    """V-φ characterisation of one MZM measurement."""

    wafer: str
    session: str
    die: str
    fsr_nm: float
    dlambda_dv_pm_per_v: float
    vpi_v: float
    vpi_l_v_cm: float        # V·cm (figure of merit)
    phaseshifter_length_um: float
    er_db_at_minus_2v: float
    er_db_at_0v: float


def extract_phase_features(
    measurements: list[Measurement],
    mzm_features: pd.DataFrame,
) -> pd.DataFrame:
    """Add Vπ / Vπ·L / ER columns derived from the MZM extractor output.

    Parameters
    ----------
    measurements : list[Measurement]
        Parsed DCM_LMZO measurements (needed to compute ER from raw spectra).
    mzm_features : pandas.DataFrame
        Output of :func:`picqa.extract.mzm.extract_mzm_features`. Must contain
        ``Wafer, Session, Die, FSR_nm, dLambda_dV_pm_per_V``.

    Returns
    -------
    pandas.DataFrame
        Same number of rows as ``mzm_features``, with new columns appended:
        ``Vpi_V``, ``Vpi_L_V_cm``, ``PhaseShifter_Length_um``,
        ``ER_at_-2V_dB``, ``ER_at_0V_dB``.
    """
    if mzm_features.empty:
        out = mzm_features.copy()
        for col in ["Vpi_V", "Vpi_L_V_cm", "PhaseShifter_Length_um",
                    "ER_at_-2V_dB", "ER_at_0V_dB"]:
            out[col] = pd.Series(dtype=float)
        return out

    # Index measurements for fast lookup by (wafer, session, die)
    meas_by_key = {
        (m.wafer, m.session, m.die): m
        for m in measurements
        if m.test_site == "DCM_LMZO"
    }

    rows: list[dict] = []
    for _, r in mzm_features.iterrows():
        key = (r["Wafer"], r["Session"], r["Die"])
        m = meas_by_key.get(key)

        # Vπ
        slope_pm_per_v = r.get("dLambda_dV_pm_per_V", float("nan"))
        slope_nm_per_v = (slope_pm_per_v / 1000.0) if pd.notna(slope_pm_per_v) else float("nan")
        fsr = r.get("FSR_nm", float("nan"))
        vpi = vpi_from_slope(slope_nm_per_v, fsr)

        # Vπ·L (cm·V)
        L_um = parse_phaseshifter_length_um(m.device_name) if m is not None else float("nan")
        if np.isfinite(vpi) and np.isfinite(L_um):
            vpi_l = vpi * (L_um * 1e-4)  # µm → cm
        else:
            vpi_l = float("nan")

        # ER at two biases
        er_m2 = float("nan")
        er_0 = float("nan")
        if m is not None:
            sw_m2 = m.sweep_at_bias(-2.0)
            sw_0 = m.sweep_at_bias(0.0)
            if sw_m2 is not None:
                er_m2 = extinction_ratio_db(sw_m2)
            if sw_0 is not None:
                er_0 = extinction_ratio_db(sw_0)

        rows.append({
            "Vpi_V": vpi,
            "Vpi_L_V_cm": vpi_l,
            "PhaseShifter_Length_um": L_um,
            "ER_at_-2V_dB": er_m2,
            "ER_at_0V_dB": er_0,
        })

    add_df = pd.DataFrame(rows, index=mzm_features.index)
    return pd.concat([mzm_features.reset_index(drop=True),
                      add_df.reset_index(drop=True)], axis=1)


# --------------------------------------------------------------------- #
# V-φ trace for a single die (for plotting)
# --------------------------------------------------------------------- #
def vphi_trace(measurement: Measurement) -> pd.DataFrame:
    """Build a V vs Δφ table for one die's MZM measurement.

    Returns a DataFrame with columns ``[Bias_V, Notch_nm, dPhi_rad,
    dPhi_over_pi]``. Empty DataFrame if the measurement is unusable.
    """
    from scipy.signal import find_peaks

    cols = ["Bias_V", "Notch_nm", "dPhi_rad", "dPhi_over_pi"]
    if not measurement.sweeps:
        return pd.DataFrame(columns=cols)

    sweeps_sorted = sorted(measurement.sweeps, key=lambda s: s.dc_bias_v)
    sw0 = next((s for s in sweeps_sorted if abs(s.dc_bias_v) < 0.01), None)
    if sw0 is None:
        return pd.DataFrame(columns=cols)

    notches_0, _ = find_peaks(-sw0.insertion_loss_db, prominence=8.0)
    if notches_0.size == 0:
        return pd.DataFrame(columns=cols)

    seed_lambda = float(sw0.wavelength_nm[notches_0[
        int(np.argmin(np.abs(sw0.wavelength_nm[notches_0] - 1310.0)))
    ]])
    fsr = float(np.median(np.diff(sw0.wavelength_nm[notches_0]))) \
        if notches_0.size >= 2 else float("nan")

    biases = []
    lambdas = []
    ref_lam = seed_lambda
    half_fsr = fsr / 2.0 if np.isfinite(fsr) else 5.0

    for s in sweeps_sorted:
        peaks, _ = find_peaks(-s.insertion_loss_db, prominence=8.0)
        if peaks.size == 0:
            continue
        nls = s.wavelength_nm[peaks]
        j = int(np.argmin(np.abs(nls - ref_lam)))
        if abs(nls[j] - ref_lam) > half_fsr:
            continue
        biases.append(s.dc_bias_v)
        lambdas.append(float(nls[j]))
        ref_lam = float(nls[j])

    biases_arr = np.asarray(biases, dtype=float)
    lambdas_arr = np.asarray(lambdas, dtype=float)
    if biases_arr.size == 0:
        return pd.DataFrame(columns=cols)

    dphi = voltage_to_phase(biases_arr, lambdas_arr, fsr)
    return pd.DataFrame({
        "Bias_V": biases_arr,
        "Notch_nm": lambdas_arr,
        "dPhi_rad": dphi,
        "dPhi_over_pi": dphi / np.pi,
    })
