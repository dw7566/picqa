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

    # PN modulator analysis (independent parser/extractor)
    pn_seg_df = pd.DataFrame()
    pn_fit_df = pd.DataFrame()
    try:
        from picqa.extract.pn_modulator import (
            extract_pn_length_fit,
            extract_pn_segment_features,
        )
        from picqa.io.pn_parser import parse_pn_directory
        pn_measurements = parse_pn_directory(data_dir)
        if pn_measurements:
            pn_seg_df = extract_pn_segment_features(pn_measurements)
            pn_fit_df = extract_pn_length_fit(pn_seg_df)
            pn_seg_df.to_csv(out_dir / "pn_segments.csv", index=False)
            pn_fit_df.to_csv(out_dir / "pn_length_fit.csv", index=False)
    except Exception as exc:
        # PN data is optional; don't break the whole report
        import logging
        logging.getLogger(__name__).warning("PN analysis skipped: %s", exc)

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

    # PN figures
    if not pn_seg_df.empty:
        try:
            from picqa.viz.pn_plot import plot_pn_length_dependence, plot_pn_summary
            fig_paths["pn_length"] = plot_pn_length_dependence(
                pn_seg_df, fig_dir / "pn_length.png"
            )
            if not pn_fit_df.empty:
                fig_paths["pn_summary"] = plot_pn_summary(
                    pn_fit_df, fig_dir / "pn_summary.png"
                )
        except Exception:
            fig_paths["pn_length"] = None
            fig_paths["pn_summary"] = None

    # Project 1: wafer-level uniformity analysis
    uniformity_dfs = {}
    try:
        from picqa.analysis.wafer_uniformity import (
            center_vs_edge,
            fsr_to_index_variation,
            iv_uniformity,
        )
        from picqa.viz.uniformity_plot import (
            plot_center_vs_edge,
            plot_radial_dependence,
        )
        uniformity_dfs["cve_il"] = center_vs_edge(
            features, "PeakIL_near_1310_dB", group_by=["Wafer"]
        )
        uniformity_dfs["fsr_var"] = fsr_to_index_variation(
            features, group_by=["Wafer", "Session"]
        )
        uniformity_dfs["iv_uni"] = iv_uniformity(
            features, metric="I_at_-1V_pA", group_by=["Wafer", "Session"]
        )
        uniformity_dfs["cve_il"].to_csv(out_dir / "center_vs_edge_il.csv", index=False)
        uniformity_dfs["fsr_var"].to_csv(out_dir / "fsr_index_variation.csv", index=False)
        uniformity_dfs["iv_uni"].to_csv(out_dir / "iv_uniformity.csv", index=False)
        fig_paths["radial_il"] = plot_radial_dependence(
            features, "PeakIL_near_1310_dB", fig_dir / "radial_il.png",
            title="Grating coupler IL vs wafer radius",
        )
        fig_paths["center_vs_edge"] = plot_center_vs_edge(
            features,
            ["FSR_nm", "PeakIL_near_1310_dB", "I_at_-1V_pA"],
            fig_dir / "center_vs_edge.png",
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Uniformity analysis skipped: %s", exc)

    # Project 2: V-phi extraction (Vπ, Vπ·L, ER)
    phase_df = pd.DataFrame()
    try:
        from picqa.analysis.phase_extraction import extract_phase_features
        from picqa.viz.uniformity_plot import plot_vpi_distribution, plot_vphi_curve
        phase_df = extract_phase_features(measurements, features)
        phase_df.to_csv(out_dir / "phase_features.csv", index=False)
        # Pick a representative working die for the V-phi curve
        good = phase_df[~phase_df.get("FailedContact", pd.Series(False, index=phase_df.index))]
        if not good.empty:
            row0 = good.iloc[0]
            target = next(
                (m for m in measurements
                 if m.wafer == row0["Wafer"] and m.session == row0["Session"]
                 and m.die == row0["Die"]),
                None,
            )
            if target is not None:
                fig_paths["vphi"] = plot_vphi_curve(target, fig_dir / "vphi_curve.png")
        fig_paths["vpi_dist"] = plot_vpi_distribution(
            phase_df, fig_dir / "vpi_distribution.png"
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Phase extraction skipped: %s", exc)

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

    # Project 1: wafer-level uniformity analysis
    if uniformity_dfs:
        lines.append("## Project 1 — Wafer-level process uniformity")
        lines.append("")
        if "cve_il" in uniformity_dfs and not uniformity_dfs["cve_il"].empty:
            lines.append("### Grating coupler IL: center vs edge dies")
            lines.append("")
            lines.append("Edge_radius threshold = 2.5 die-units (R ≤ 2.5 → center).")
            lines.append("")
            lines.append(_df_to_md(uniformity_dfs["cve_il"]))
            lines.append("")
        if "fsr_var" in uniformity_dfs and not uniformity_dfs["fsr_var"].empty:
            lines.append("### FSR variation → implied geometry / index variation")
            lines.append("")
            lines.append("`FSR_relative_variation_pct = σ(FSR) / mean(FSR) × 100`. "
                         "For an unbalanced MZI, this approximates Δn_g/n_g, which in turn "
                         "reflects waveguide width / thickness uniformity across the wafer.")
            lines.append("")
            lines.append(_df_to_md(uniformity_dfs["fsr_var"]))
            lines.append("")
        if "iv_uni" in uniformity_dfs and not uniformity_dfs["iv_uni"].empty:
            lines.append("### IV uniformity (leakage at -1 V)")
            lines.append("")
            lines.append("Per-session statistics including robust median + MAD-based σ "
                         "alongside parametric mean / std / CV. Sessions with failed contact "
                         "show extremely low absolute means (~100 pA) compared to working "
                         "ones (10⁴–10⁵ pA).")
            lines.append("")
            lines.append(_df_to_md(uniformity_dfs["iv_uni"]))
            lines.append("")

    # Project 2: V-phi
    if not phase_df.empty:
        lines.append("## Project 2 — Voltage-based phase modulator characterisation")
        lines.append("")
        n_with_vpi = int(phase_df["Vpi_V"].notna().sum())
        lines.append(f"Extracted Vπ, Vπ·L, and extinction ratio for {n_with_vpi}/{len(phase_df)} dies. "
                     f"Vπ = FSR / (2·|dλ/dV|). Phase-shifter length is parsed best-effort from "
                     f"the device name; if absent, Vπ·L is left as NaN.")
        lines.append("")
        per_wafer_vpi = (
            phase_df[~phase_df["FailedContact"]]
            .groupby("Wafer")[["Vpi_V", "Vpi_L_V_cm", "ER_at_-2V_dB"]]
            .agg(["count", "median", "std"])
            .round(3)
        )
        if not per_wafer_vpi.empty:
            lines.append("### Per-wafer Vπ summary (working dies)")
            lines.append("")
            # Flatten multi-index columns for prettier markdown
            flat = per_wafer_vpi.copy()
            flat.columns = [f"{a}_{b}" for a, b in flat.columns]
            flat = flat.reset_index()
            lines.append(_df_to_md(flat))
            lines.append("")

    # PN modulator section
    if not pn_seg_df.empty:
        lines.append("## PN modulator (PCM_PSLOTE_P1N1) analysis")
        lines.append("")
        lines.append(f"Extracted {len(pn_seg_df)} segment rows over {len(pn_fit_df)} dies. "
                     f"Each die has three PN segments (typically 500 / 1500 / 2500 µm) plus a "
                     f"reference waveguide; per-µm doping loss and electroabsorption "
                     f"modulation efficiency are obtained by linear fits versus segment length.")
        lines.append("")
        lines.append("### Per-die length-fit results (first 20 rows)")
        lines.append("")
        lines.append(_df_to_md(pn_fit_df.head(20)))
        lines.append("")

    lines.append("## Figures")
    lines.append("")
    if fig_paths.get("iv"):
        lines.append("### IV characteristics (MZM)")
        lines.append(f"![IV]({fig_paths['iv'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("spectra"):
        lines.append("### Transmission spectra @ -2V (MZM)")
        lines.append(f"![Spectra]({fig_paths['spectra'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("bias"):
        lines.append("### Bias-dependent spectrum (representative MZM die)")
        lines.append(f"![Bias shift]({fig_paths['bias'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("wafermap"):
        lines.append("### MZM wafer maps")
        lines.append(f"![Wafer maps]({fig_paths['wafermap'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("summary"):
        lines.append("### MZM summary panels")
        lines.append(f"![Summary]({fig_paths['summary'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("pn_length"):
        lines.append("### PN modulator length dependence")
        lines.append(f"![PN length]({fig_paths['pn_length'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("pn_summary"):
        lines.append("### PN modulator summary panels")
        lines.append(f"![PN summary]({fig_paths['pn_summary'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("radial_il"):
        lines.append("### (Project 1) Grating coupler IL vs wafer radius")
        lines.append(f"![Radial IL]({fig_paths['radial_il'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("center_vs_edge"):
        lines.append("### (Project 1) Center vs edge boxplots")
        lines.append(f"![Center vs edge]({fig_paths['center_vs_edge'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("vphi"):
        lines.append("### (Project 2) Representative V-φ curve")
        lines.append(f"![V-phi curve]({fig_paths['vphi'].relative_to(out_dir)})")
        lines.append("")
    if fig_paths.get("vpi_dist"):
        lines.append("### (Project 2) Vπ distribution and Vπ·L figure of merit")
        lines.append(f"![Vπ distribution]({fig_paths['vpi_dist'].relative_to(out_dir)})")
        lines.append("")

    md_path = out_dir / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path
