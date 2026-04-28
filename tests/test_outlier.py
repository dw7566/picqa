"""Tests for picqa.analysis.outlier."""

from __future__ import annotations

import pandas as pd

from picqa.analysis.outlier import flag_failed_contacts, working_only


def test_flag_failed_contacts_marks_low_slope():
    df = pd.DataFrame(
        [
            {"dLambda_dV_pm_per_V": -180, "I_at_-1V_pA": 5e4},  # working
            {"dLambda_dV_pm_per_V": -1.0,  "I_at_-1V_pA": 5e4},  # failed (slope)
            {"dLambda_dV_pm_per_V": -180, "I_at_-1V_pA": 100},  # failed (leakage)
        ]
    )
    flagged = flag_failed_contacts(df)
    assert flagged.iloc[0]["FailedContact"] == False  # noqa: E712
    assert flagged.iloc[1]["FailedContact"] == True  # noqa: E712
    assert flagged.iloc[2]["FailedContact"] == True  # noqa: E712


def test_working_only_filters():
    df = pd.DataFrame(
        [
            {"dLambda_dV_pm_per_V": -180, "I_at_-1V_pA": 5e4},
            {"dLambda_dV_pm_per_V": -1.0,  "I_at_-1V_pA": 5e4},
        ]
    )
    out = working_only(df)
    assert len(out) == 1
    assert out.iloc[0]["dLambda_dV_pm_per_V"] == -180


def test_flag_handles_missing_columns_gracefully():
    df = pd.DataFrame([{"Other": 1}])
    out = flag_failed_contacts(df)
    # No metric columns means no row passes the slope/leakage tests, so all flagged
    assert "FailedContact" in out.columns


def test_flag_handles_nan_as_failed():
    df = pd.DataFrame([{"dLambda_dV_pm_per_V": float("nan"), "I_at_-1V_pA": float("nan")}])
    flagged = flag_failed_contacts(df)
    assert flagged.iloc[0]["FailedContact"] == True  # noqa: E712
