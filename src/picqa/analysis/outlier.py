"""Heuristic detection of failed-contact measurements.

When the probe loses electrical contact with the device under test, the IV
sweep flattens at the SMU's noise floor and the modulator does not respond to
bias. We can flag these in two ways:

1. **Tuning slope test**: |dλ/dV| below a threshold (e.g. 30 pm/V) means the
   junction is not modulating. Robust because the optical channel is
   independent of electrical contact.
2. **IV magnitude test**: |I| at -1V below a noise-floor threshold (e.g. 1 nA)
   indicates the SMU is reading nothing.

Both signals can be combined.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def flag_failed_contacts(
    features: pd.DataFrame,
    *,
    slope_threshold_pm_per_v: float = 30.0,
    leakage_threshold_pa: float = 1_000.0,
) -> pd.DataFrame:
    """Add a ``FailedContact`` boolean column to a feature DataFrame.

    A row is flagged if **either**:

    * |dLambda_dV_pm_per_V| is below ``slope_threshold_pm_per_v``, or
    * |I_at_-1V_pA| is below ``leakage_threshold_pa``.

    Missing values are conservatively treated as failures.
    """
    out = features.copy()

    if "dLambda_dV_pm_per_V" in out.columns:
        slope_fail = out["dLambda_dV_pm_per_V"].abs().fillna(0) < slope_threshold_pm_per_v
    else:
        slope_fail = pd.Series([False] * len(out), index=out.index)

    if "I_at_-1V_pA" in out.columns:
        leak_fail = out["I_at_-1V_pA"].abs().fillna(0) < leakage_threshold_pa
    else:
        leak_fail = pd.Series([False] * len(out), index=out.index)

    out["FailedContact"] = (slope_fail | leak_fail).astype(bool)
    return out


def working_only(features: pd.DataFrame) -> pd.DataFrame:
    """Return only rows that are **not** flagged as failed contacts.

    If ``FailedContact`` is missing, this calls :func:`flag_failed_contacts`
    with default thresholds first.
    """
    df = features if "FailedContact" in features.columns else flag_failed_contacts(features)
    return df[~df["FailedContact"]].copy()
