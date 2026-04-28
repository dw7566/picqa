"""Generate a self-contained Markdown report.

The report bundles inventory, MZM features, statistics, yield (if a spec is
provided), and embedded PNG figures into a single Markdown file.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from picqa.analysis.outlier import flag_failed_contacts
from picqa.analysis.statistics import per_group_stats
from picqa.analysis.yield_calc import Spec, evaluate_yield, yield_summary
from picqa.extract.mzm import extract_mzm_features
from picqa.io.schemas import Measurement
from picqa.io.xml_parser import inventory, parse_directory
from picqa.viz.iv_plot import plot_iv_grid
from picqa.viz.spectrum_plot import plot_bias_shift, plot_spectra_grid
from picqa.viz.summary_plot import plot_summary
from picqa.viz.wafer_map import plot_wafermap_grid


METRICS_FOR_STATS = [
    "FSR_nm",
    "Notch_at_0V_nm",
    "dLambda_dV_pm_per_V",
    "PeakIL_near_1310_dB",
    "I_at_-1V_pA",
]


def _df_to_md(df: pd.DataFrame, *, max_rows: int = 50) -> str:
    """Convert a DataFrame to a GitHub-flavoured Markdown table.

    Uses ``pandas.DataFrame.to_markdown`` if the ``tabulate`` dependency is
    available, otherwise falls back to a simple hand-rolled formatter so the
    library has no hard runtime dependency on tabulate.
    """
    if df.empty:
        return "_(empty)_"
    if len(df) > max_rows:
        df = df.head(max_rows)
    try:
        return df.to_markdown(index=False, floatfmt=".4g")
    except ImportError:
        return _df_to_md_fallback(df)


def _df_to_md_fallback(df: pd.DataFrame) -> str:
    """Minimal Markdown table renderer (no external deps)."""
    def _fmt(v):
        if isinstance(v, float):
            return f"{v:.4g}"
        return str(v)

    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |"]
    lines.append("|" + "|".join("---" for _ in cols) + "|")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(row[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def generate_report(
    data_dir: str | Path,
    output_dir: str | Path,
    *,
    spec: Spec | None = None,
    measurements: list[Measurement] | None = None,
    title: str = "PICQA Analysis Report",
) -> Path:
    """Run the full analysis pipeline and write a Markdown report.

    Parameters
    ----------
    data_dir : str | Path
        Directory containing the raw XML measurement files.
    output_dir : str | Path
        Where to write the report and its figures.
    spec : Spec | None
        If provided, a yield evaluation section is added.
    measurements : list[Measurement] | None
        Pre-parsed measurements. If ``None``, parses ``data_dir`` directly.
    title : str
        Title for the report.

    Returns
    -------
    Path
        Path to ``report.md``.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(exist_ok=True)

    inv = inventory(data_dir)
    if measurements is None:
        measurements = parse_directory(data_dir, test_site="DCM_LMZO")

    features = extract_mzm_features(measurements)
    features = flag_failed_contacts(features)
    features.to_csv(out_dir / "mzm_features.csv", index=False)

    # Figures (skip gracefully if data missing)
    fig_paths: dict[str, Path | None] = {}
    try:
        fig_paths["iv"] = plot_iv_grid(measurements, fig_dir / "iv.png")
    except Exception:
        fig_paths["iv"] = None
    try:
        fig_paths["spectra"] = plot_spectra_grid(measurements, fig_dir / "spectra.png")
    except Exception:
        fig_paths["spectra"] = None
    try:
        # bias-shift: pick first measurement that is not flagged as failed contact
        good_dies = features[~features["FailedContact"]]
        if not good_dies.empty:
            row = good_dies.iloc[0]
            target = next(
                (m for m in measurements
                 if m.wafer == row["Wafer"]
                 and m.session == row["Session"]
                 and m.die == row["Die"]),
                None,
            )
            if target:
                fig_paths["bias"] = plot_bias_shift(target, fig_dir / "bias_shift.png")
            else:
                fig_paths["bias"] = None
        else:
            fig_paths["bias"] = None
    except Exception:
        fig_paths["bias"] = None
    try:
        fig_paths["wafermap"] = plot_wafermap_grid(
            features,
            metrics=["I_at_-1V_pA", "PeakIL_near_1310_dB"],
            output_path=fig_dir / "wafermaps.png",
        )
    except Exception:
        fig_paths["wafermap"] = None
    try:
        fig_paths["summary"] = plot_summary(features, fig_dir / "summary.png")
    except Exception:
        fig_paths["summary"] = None

    # Statistics
    stats = per_group_stats(features, group_by=["Wafer", "Session"], metrics=METRICS_FOR_STATS)
    stats.to_csv(out_dir / "stats_per_session.csv", index=False)

    # Yield (optional)
    yield_section = ""
    if spec is not None:
        evaluated = evaluate_yield(features, spec)
        evaluated.to_csv(out_dir / "yield_per_die.csv", index=False)
        per_wafer = yield_summary(evaluated, group_by=["Wafer"])
        per_session = yield_summary(evaluated, group_by=["Wafer", "Session"])
        per_wafer.to_csv(out_dir / "yield_per_wafer.csv", index=False)
        per_session.to_csv(out_dir / "yield_per_session.csv", index=False)
        yield_section = (
            "## Yield evaluation\n\n"
            f"Spec: `{spec.name}` with rules: `{spec.rules}`\n\n"
            "### Per-wafer yield\n\n"
            f"{_df_to_md(per_wafer)}\n\n"
            "### Per-session yield\n\n"
            f"{_df_to_md(per_session)}\n"
        )

    # Compose Markdown
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"_Generated {timestamp} by picqa._")
    lines.append("")
    lines.append("## Inventory")
    lines.append("")
    lines.append(f"- Source directory: `{Path(data_dir).resolve()}`")
    lines.append(f"- Total XML files: **{inv['n_files']}** "
                 f"({inv['total_size_bytes']/1e6:.1f} MB)")
    lines.append("- Files per wafer: " + ", ".join(
        f"{k}={v}" for k, v in inv["by_wafer"].items()
    ))
    lines.append("")
    lines.append("### Test site distribution")
    lines.append("")
    lines.append("| Test site | Count |")
    lines.append("|---|---|")
    for k, v in inv["by_test_site"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## MZM feature extraction")
    lines.append("")
    lines.append(f"Extracted {len(features)} MZM measurements from `DCM_LMZO`. "
                 f"Failed-contact flag added via leakage + tuning-slope thresholds.")
    if "FailedContact" in features.columns:
        n_fail = int(features["FailedContact"].sum())
        lines.append(f"Flagged as failed-contact: **{n_fail} / {len(features)}**")
    lines.append("")
    lines.append("Sample of features (first 20 rows):")
    lines.append("")
    lines.append(_df_to_md(features.head(20)))
    lines.append("")

    lines.append("## Robust statistics per (wafer, session)")
    lines.append("")
    lines.append(_df_to_md(stats))
    lines.append("")

    if yield_section:
        lines.append(yield_section)

    lines.append("## Figures")
    lines.append("")
    if fig_paths.get("iv"):
        lines.append("### IV characteristics")
        lines.append(f"![IV]({fig_paths['iv'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("spectra"):
        lines.append("### Transmission spectra @ -2V")
        lines.append(f"![Spectra]({fig_paths['spectra'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("bias"):
        lines.append("### Bias-dependent spectrum (representative die)")
        lines.append(f"![Bias shift]({fig_paths['bias'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("wafermap"):
        lines.append("### Wafer maps")
        lines.append(f"![Wafer maps]({fig_paths['wafermap'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("summary"):
        lines.append("### Summary panels")
        lines.append(f"![Summary]({fig_paths['summary'].relative_to(out_dir)})")
        lines.append("")

    md_path = out_dir / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path
