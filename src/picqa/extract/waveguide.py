"""Extract waveguide propagation loss via the cut-back method.

A spiral set (e.g. ``OTEST_L3OTE``) contains multiple physical lengths of the
same waveguide cross-section. Plotting IL vs length gives a straight line whose
slope is the propagation loss in dB/length-unit; the intercept is the fixed
coupler insertion loss.

This module does not consume those length-dependent files in this initial
version because the dataset's encoding of per-arm IL requires per-port parsing
that is out of scope for the CLI demo. The function below is a placeholder that
returns an empty DataFrame so downstream code does not crash. It documents the
intended interface for future implementation.
"""

from __future__ import annotations

import pandas as pd

from picqa.io.schemas import Measurement


WAVEGUIDE_TEST_SITES = {"OTEST_L3OTE", "OTEST_L4OTE", "PCM_L_EXPO"}


def extract_waveguide_loss(measurements: list[Measurement]) -> pd.DataFrame:
    """Extract per-die propagation loss (dB/cm) from spiral test data.

    Returns
    -------
    pandas.DataFrame
        Columns: ``Wafer, Session, Die, DieCol, DieRow, Device,
        Loss_dB_per_cm, Coupling_Loss_dB``.

    Notes
    -----
    Currently returns an empty frame. Implementing this requires reading
    per-spiral IL values from the XML's ``PortLossMeasurement`` blocks and
    fitting a line over the design-parameter ``Lengths`` array.
    """
    columns = [
        "Wafer", "Session", "Die", "DieCol", "DieRow", "Device",
        "Loss_dB_per_cm", "Coupling_Loss_dB",
    ]
    return pd.DataFrame(columns=columns)
