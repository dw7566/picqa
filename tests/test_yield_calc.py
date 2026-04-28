"""Tests for picqa.analysis.yield_calc."""

from __future__ import annotations

import pandas as pd
import pytest

from picqa.analysis.yield_calc import (
    Spec,
    evaluate_yield,
    load_spec,
    yield_summary,
)


@pytest.fixture
def sample_features():
    return pd.DataFrame(
        [
            {"Wafer": "D08", "Die": "(0,0)", "I_at_-1V_pA": 5e4, "dLambda_dV_pm_per_V": -180},
            {"Wafer": "D08", "Die": "(1,1)", "I_at_-1V_pA": 1e7, "dLambda_dV_pm_per_V": -180},
            {"Wafer": "D24", "Die": "(0,0)", "I_at_-1V_pA": 2e5, "dLambda_dV_pm_per_V": -130},
            {"Wafer": "D24", "Die": "(1,1)", "I_at_-1V_pA": 2e5, "dLambda_dV_pm_per_V": -50},
        ]
    )


@pytest.fixture
def sample_spec():
    return Spec(
        name="mzm",
        rules={
            "I_at_-1V_pA": {"max_abs": 1e6},  # ≤ 1 µA
            "dLambda_dV_pm_per_V": {"min_abs": 100},  # ≥ 100 pm/V
        },
    )


def test_evaluate_yield_marks_pass_correctly(sample_features, sample_spec):
    out = evaluate_yield(sample_features, sample_spec)
    assert "Pass" in out.columns
    assert "Pass_I_at_-1V_pA" in out.columns
    # First die: low leakage, good slope → pass
    assert out.iloc[0]["Pass"]
    # Second die: leakage too high → fail
    assert not out.iloc[1]["Pass"]
    # Fourth die: slope too low → fail
    assert not out.iloc[3]["Pass"]


def test_evaluate_yield_handles_missing_metric(sample_features):
    spec = Spec(name="mzm", rules={"NonexistentMetric": {"min": 0}})
    out = evaluate_yield(sample_features, spec)
    assert (out["Pass_NonexistentMetric"] == False).all()  # noqa: E712


def test_evaluate_yield_empty_input_returns_empty(sample_spec):
    df = pd.DataFrame(columns=["Wafer", "Die", "I_at_-1V_pA", "dLambda_dV_pm_per_V"])
    out = evaluate_yield(df, sample_spec)
    assert out.empty
    assert "Pass" in out.columns


def test_yield_summary_per_wafer(sample_features, sample_spec):
    evaluated = evaluate_yield(sample_features, sample_spec)
    summary = yield_summary(evaluated, group_by=["Wafer"])
    assert set(summary.columns) >= {"Wafer", "n_total", "n_pass", "yield_pct"}
    d08 = summary[summary["Wafer"] == "D08"].iloc[0]
    assert d08["n_total"] == 2
    assert d08["n_pass"] == 1
    assert d08["yield_pct"] == 50.0


def test_yield_summary_overall_when_no_groupby(sample_features, sample_spec):
    evaluated = evaluate_yield(sample_features, sample_spec)
    summary = yield_summary(evaluated)
    assert len(summary) == 1
    assert summary.iloc[0]["n_total"] == 4
    # D08(0,0), D24(0,0) pass; D08(1,1) fails on leakage; D24(1,1) fails on slope
    assert summary.iloc[0]["n_pass"] == 2


def test_load_spec_from_yaml(tmp_path):
    yaml_text = (
        "mzm:\n"
        "  I_at_-1V_pA:\n"
        "    max_abs: 1.0e6\n"
        "  dLambda_dV_pm_per_V:\n"
        "    min_abs: 100\n"
    )
    p = tmp_path / "spec.yaml"
    p.write_text(yaml_text)
    spec = load_spec(p, "mzm")
    assert spec.name == "mzm"
    assert "I_at_-1V_pA" in spec.rules


def test_load_spec_raises_for_unknown_family(tmp_path):
    p = tmp_path / "spec.yaml"
    p.write_text("mzm:\n  I:\n    max: 1\n")
    with pytest.raises(KeyError):
        load_spec(p, "unknown_family")
