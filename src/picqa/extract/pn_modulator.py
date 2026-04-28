"""Extract PN modulator (PCM_PSLOTE_P1N1) characteristics.

The PN modulator test site contains three PN segments of different active
lengths (typically 500, 1500, 2500 µm) plus one reference port (a bare
waveguide with no PN doping). The reference is used to back out the doping
contribution from the total insertion loss.

Per segment we extract the same kinds of metrics as the MZM extractor —
notch wavelength, tuning slope, leakage — and additionally the IL increase
versus the reference port. We then fit those vs length to obtain
**per-unit-length** parameters that characterise the doped waveguide
itself, independently of fixed coupler losses.

Two output frames are produced:

* ``segment_features`` — one row per (die, segment_length).
* ``length_fit_features`` — one row per die, with linear-fit slopes and
  intercepts over the three lengths.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from picqa.io.pn_schemas import PNMeasurement, PNSegment

logger = logging.getLogger(__name__)

DESIGN_WAVELENGTH_NM = 1310.0


# ----------------------------------------------------------------------- #
# Helpers
# ----------------------------------------------------------------------- #
def _absorption_slope_db_per_v(seg: PNSegment, near: float = DESIGN_WAVELENGTH_NM) -> float:
    """Linear fit of IL@1310nm vs DC bias (returns dB/V).

    PN modulators in this dataset are single waveguides without an
    interferometer, so they do not exhibit transmission notches; they modulate
    primarily through carrier-induced electroabsorption (and a small
    refractive contribution). The simplest robust metric is therefore the
    IL change at the design wavelength as a function of bias.
    """
    if len(seg.sweeps) < 3:
        return float("nan")
    biases = np.array([s.dc_bias_v for s in seg.sweeps], dtype=float)
    ils = np.array(
        [float(np.interp(near, s.wavelength_nm, s.insertion_loss_db))
         for s in seg.sweeps],
        dtype=float,
    )
    if not np.all(np.isfinite(biases)) or not np.all(np.isfinite(ils)):
        return float("nan")
    slope, _ = np.polyfit(biases, ils, 1)
    return float(slope)


def _segment_features(seg: PNSegment, ref_il_at_1310: float | None) -> dict:
    """Extract metrics for one active segment."""
    out = {
        "Length_um": seg.length_um,
        "PortLabel": seg.port_label,
        "PeakIL_at_1310_dB": float("nan"),
        "IL_drop_vs_REF_dB": float("nan"),
        "dIL_dV_dB_per_V": float("nan"),
        "I_at_-1V_pA": float("nan"),
        "I_at_-2V_pA": float("nan"),
    }

    sw0 = seg.sweep_at_bias(0.0)
    if sw0 is not None:
        # IL at 1310 (interpolated, so we don't depend on grid alignment)
        il_at_1310 = float(np.interp(DESIGN_WAVELENGTH_NM,
                                     sw0.wavelength_nm,
                                     sw0.insertion_loss_db))
        out["PeakIL_at_1310_dB"] = il_at_1310
        if ref_il_at_1310 is not None and not np.isnan(il_at_1310):
            out["IL_drop_vs_REF_dB"] = il_at_1310 - ref_il_at_1310

    out["dIL_dV_dB_per_V"] = _absorption_slope_db_per_v(seg)

    if seg.iv is not None:
        out["I_at_-1V_pA"] = seg.iv.at(-1.0) * 1e12
        out["I_at_-2V_pA"] = seg.iv.at(-2.0) * 1e12

    return out


def extract_pn_segment_features(measurements: list[PNMeasurement]) -> pd.DataFrame:
    """One row per (die, segment_length)."""
    rows: list[dict] = []
    for m in measurements:
        ref_il = None
        if m.reference is not None:
            sw0 = m.reference.sweep_at_bias(0.0)
            if sw0 is not None:
                ref_il = float(np.interp(DESIGN_WAVELENGTH_NM,
                                         sw0.wavelength_nm,
                                         sw0.insertion_loss_db))

        for seg in m.active_segments:
            base = {
                "Wafer": m.wafer,
                "Session": m.session,
                "Die": m.die,
                "DieCol": m.die_col,
                "DieRow": m.die_row,
            }
            base.update(_segment_features(seg, ref_il))
            rows.append(base)

    columns = [
        "Wafer", "Session", "Die", "DieCol", "DieRow", "PortLabel",
        "Length_um", "PeakIL_at_1310_dB", "IL_drop_vs_REF_dB",
        "dIL_dV_dB_per_V",
        "I_at_-1V_pA", "I_at_-2V_pA",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def _linfit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Linear least-squares with R²; returns (slope, intercept, r2)."""
    if x.size < 2 or np.any(~np.isfinite(y)) or np.any(~np.isfinite(x)):
        return float("nan"), float("nan"), float("nan")
    slope, intercept = np.polyfit(x, y, 1)
    y_hat = slope * x + intercept
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return float(slope), float(intercept), r2


def extract_pn_length_fit(segment_features: pd.DataFrame) -> pd.DataFrame:
    """Per-die linear fits of metrics vs segment length.

    Adds the cleanest interpretation:

    * ``IL_drop_vs_REF_dB`` is expected to scale linearly with length, so the
      slope gives the **per-µm doping loss** (dB/µm).
    * ``dIL_dV_dB_per_V`` (electroabsorption modulation depth) is also
      expected to scale with length, giving the **per-µm modulation
      efficiency** (dB/V/µm).
    """
    rows: list[dict] = []
    if segment_features.empty:
        cols = [
            "Wafer", "Session", "Die", "DieCol", "DieRow",
            "n_lengths",
            "Loss_per_um_dB_per_um", "Loss_intercept_dB", "Loss_R2",
            "Modulation_per_um_dB_per_V_per_um",
            "Modulation_intercept_dB_per_V", "Modulation_R2",
        ]
        return pd.DataFrame(columns=cols)

    for keys, sub in segment_features.groupby(["Wafer", "Session", "Die"]):
        sub = sub.dropna(subset=["Length_um"]).sort_values("Length_um")
        L = sub["Length_um"].to_numpy(dtype=float)

        y_loss = sub["IL_drop_vs_REF_dB"].to_numpy(dtype=float)
        m_loss, b_loss, r2_loss = _linfit(L, y_loss)

        y_mod = sub["dIL_dV_dB_per_V"].to_numpy(dtype=float)
        m_mod, b_mod, r2_mod = _linfit(L, y_mod)

        wafer, session, die = keys
        die_col = int(sub.iloc[0]["DieCol"])
        die_row = int(sub.iloc[0]["DieRow"])

        rows.append({
            "Wafer": wafer, "Session": session, "Die": die,
            "DieCol": die_col, "DieRow": die_row,
            "n_lengths": len(L),
            "Loss_per_um_dB_per_um": m_loss,
            "Loss_intercept_dB": b_loss,
            "Loss_R2": r2_loss,
            "Modulation_per_um_dB_per_V_per_um": m_mod,
            "Modulation_intercept_dB_per_V": b_mod,
            "Modulation_R2": r2_mod,
        })

    return pd.DataFrame(rows)
