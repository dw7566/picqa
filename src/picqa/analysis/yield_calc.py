"""Spec-based yield evaluation.

A *spec* is a YAML file describing pass/fail criteria for one or more device
families. Example::

    mzm:
      I_at_-1V_pA:
        max: 1.0e6        # ≤ 1 µA absolute leakage
      dLambda_dV_pm_per_V:
        min_abs: 100      # |slope| ≥ 100 pm/V
      PeakIL_near_1310_dB:
        min: -10          # IL ≥ -10 dB

Supported rule keys per metric:

* ``min`` — value must be ≥ this.
* ``max`` — value must be ≤ this.
* ``min_abs`` — absolute value must be ≥ this.
* ``max_abs`` — absolute value must be ≤ this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


@dataclass
class Spec:
    """In-memory representation of a spec file for a single device family."""

    name: str
    rules: dict[str, dict[str, float]] = field(default_factory=dict)

    def metrics(self) -> list[str]:
        return list(self.rules.keys())


def load_spec(path: str | Path, family: str) -> Spec:
    """Load the named family from a YAML spec file."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if family not in data:
        raise KeyError(
            f"Spec family '{family}' not found in {p}. Available: {list(data)}"
        )
    return Spec(name=family, rules=dict(data[family]))


def _check_rule(value: float, rule: dict[str, float]) -> bool:
    """Return True if ``value`` satisfies the rule, NaN never passes."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    if "min" in rule and value < rule["min"]:
        return False
    if "max" in rule and value > rule["max"]:
        return False
    if "min_abs" in rule and abs(value) < rule["min_abs"]:
        return False
    if "max_abs" in rule and abs(value) > rule["max_abs"]:
        return False
    return True


def evaluate_yield(features: pd.DataFrame, spec: Spec) -> pd.DataFrame:
    """Apply ``spec`` to a feature table and return per-die pass/fail flags.

    The returned DataFrame contains one boolean column per metric (``Pass_<m>``)
    plus an aggregate ``Pass`` column that is True only if all rules pass.
    """
    if features.empty:
        result = features.copy()
        for metric in spec.metrics():
            result[f"Pass_{metric}"] = pd.Series(dtype=bool)
        result["Pass"] = pd.Series(dtype=bool)
        return result

    result = features.copy()
    pass_cols: list[str] = []
    for metric, rule in spec.rules.items():
        col_pass = f"Pass_{metric}"
        if metric not in result.columns:
            result[col_pass] = False
        else:
            result[col_pass] = result[metric].apply(lambda v, r=rule: _check_rule(v, r))
        pass_cols.append(col_pass)
    result["Pass"] = result[pass_cols].all(axis=1)
    return result


def yield_summary(evaluated: pd.DataFrame, group_by: list[str] | None = None) -> pd.DataFrame:
    """Summarise pass rate, optionally grouped (e.g. by Wafer or Session).

    Returns a DataFrame with columns ``[*group_by, n_total, n_pass, yield_pct]``.
    """
    if "Pass" not in evaluated.columns:
        raise ValueError("DataFrame is missing the 'Pass' column; run evaluate_yield first.")

    if not group_by:
        n_total = len(evaluated)
        n_pass = int(evaluated["Pass"].sum())
        return pd.DataFrame(
            [{"n_total": n_total, "n_pass": n_pass,
              "yield_pct": (100.0 * n_pass / n_total) if n_total else float("nan")}]
        )

    rows: list[dict] = []
    for keys, sub in evaluated.groupby(group_by, dropna=False):
        n_total = len(sub)
        n_pass = int(sub["Pass"].sum())
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_by, keys))
        row.update({
            "n_total": n_total,
            "n_pass": n_pass,
            "yield_pct": (100.0 * n_pass / n_total) if n_total else float("nan"),
        })
        rows.append(row)
    return pd.DataFrame(rows)
