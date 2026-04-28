"""Extract photodetector (DCM_GPDO) characteristics.

The Ge photodetector test files contain IV sweeps under dark and illuminated
conditions. We extract dark current at -1V (a common spec metric).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from picqa.io.schemas import Measurement

logger = logging.getLogger(__name__)


def extract_pd_features(measurements: list[Measurement]) -> pd.DataFrame:
    """Extract PD dark current features (test_site=DCM_GPDO).

    For now we report the IV-derived dark current at standard biases. Files
    that omit IV are skipped.
    """
    rows: list[dict] = []
    for m in measurements:
        if m.test_site != "DCM_GPDO":
            continue
        if m.iv is None:
            continue
        rows.append(
            {
                "Wafer": m.wafer,
                "Session": m.session,
                "Die": m.die,
                "DieCol": m.die_col,
                "DieRow": m.die_row,
                "Device": m.device_name,
                "I_dark_at_-1V_pA": m.iv.at(-1.0) * 1e12,
                "I_dark_at_-2V_pA": m.iv.at(-2.0) * 1e12,
            }
        )

    columns = [
        "Wafer", "Session", "Die", "DieCol", "DieRow", "Device",
        "I_dark_at_-1V_pA", "I_dark_at_-2V_pA",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)
