"""Command-line interface for picqa.

Subcommands::

    picqa inventory <data-dir>
    picqa parse <data-dir> [--test-site SITE] [--output FILE.pkl]
    picqa extract mzm <data-dir> [--output FILE.csv]
    picqa extract pd  <data-dir> [--output FILE.csv]
    picqa plot iv       <data-dir> --output FILE.png
    picqa plot spectra  <data-dir> --output FILE.png [--bias V]
    picqa plot wafermap <features.csv> --metric NAME --output FILE.png
    picqa plot summary  <features.csv> --output FILE.png
    picqa yield <features.csv> --spec FILE.yaml --family NAME --output FILE.csv
    picqa report <data-dir> --output-dir DIR [--spec FILE.yaml --family NAME]
"""

from __future__ import annotations

import argparse
import logging
import pickle
import sys
from pathlib import Path

import pandas as pd

from picqa import __version__
from picqa.analysis.outlier import flag_failed_contacts
from picqa.analysis.yield_calc import evaluate_yield, load_spec, yield_summary
from picqa.extract.mzm import extract_mzm_features
from picqa.extract.photodetector import extract_pd_features
from picqa.io.xml_parser import inventory, parse_directory
from picqa.report.markdown import generate_report
from picqa.viz.iv_plot import plot_iv_grid
from picqa.viz.spectrum_plot import plot_spectra_grid
from picqa.viz.summary_plot import plot_summary
from picqa.viz.wafer_map import plot_wafermap

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- #
# Subcommand handlers
# --------------------------------------------------------------------- #
def cmd_inventory(args: argparse.Namespace) -> int:
    inv = inventory(args.data_dir)
    print(f"Total files: {inv['n_files']}, {inv['total_size_bytes']/1e6:.1f} MB")
    print("Wafers:")
    for k, v in inv["by_wafer"].items():
        print(f"  {k}: {v} files")
    print("Test sites:")
    for k, v in inv["by_test_site"].items():
        print(f"  {k}: {v}")
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    measurements = parse_directory(args.data_dir, test_site=args.test_site)
    print(f"Parsed {len(measurements)} measurements")
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f:
            pickle.dump(measurements, f)
        print(f"Saved → {out}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    test_site_map = {"mzm": "DCM_LMZO", "pd": "DCM_GPDO"}

    if args.device == "pn":
        # PN modulator uses a different parser/extractor pair because its XML
        # layout (multiple PortCombo segments) doesn't fit the generic
        # Measurement schema.
        from picqa.extract.pn_modulator import (
            extract_pn_length_fit,
            extract_pn_segment_features,
        )
        from picqa.io.pn_parser import parse_pn_directory

        measurements = parse_pn_directory(args.data_dir)
        seg_df = extract_pn_segment_features(measurements)
        fit_df = extract_pn_length_fit(seg_df)

        print(f"Extracted {len(seg_df)} segment rows over {len(fit_df)} dies")
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            seg_df.to_csv(out, index=False)
            fit_path = out.with_name(out.stem + "_lengthfit.csv")
            fit_df.to_csv(fit_path, index=False)
            print(f"Per-segment → {out}")
            print(f"Length fit  → {fit_path}")
        else:
            print(seg_df.head().to_string(index=False))
        return 0

    test_site = test_site_map.get(args.device)
    measurements = parse_directory(args.data_dir, test_site=test_site)

    if args.device == "mzm":
        df = extract_mzm_features(measurements)
        df = flag_failed_contacts(df)
    elif args.device == "pd":
        df = extract_pd_features(measurements)
    else:
        print(f"Unknown device: {args.device}", file=sys.stderr)
        return 2

    print(f"Extracted {len(df)} rows")
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"Saved → {out}")
    else:
        print(df.head().to_string(index=False))
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    out = Path(args.output)

    if args.kind == "iv":
        measurements = parse_directory(args.input, test_site="DCM_LMZO")
        plot_iv_grid(measurements, out)
    elif args.kind == "spectra":
        measurements = parse_directory(args.input, test_site="DCM_LMZO")
        plot_spectra_grid(measurements, out, bias_v=args.bias)
    elif args.kind == "wafermap":
        df = pd.read_csv(args.input)
        plot_wafermap(df, args.metric, out)
    elif args.kind == "summary":
        df = pd.read_csv(args.input)
        plot_summary(df, out)
    elif args.kind == "pn_length":
        from picqa.viz.pn_plot import plot_pn_length_dependence
        df = pd.read_csv(args.input)
        plot_pn_length_dependence(df, out)
    elif args.kind == "pn_summary":
        from picqa.viz.pn_plot import plot_pn_summary
        df = pd.read_csv(args.input)
        plot_pn_summary(df, out)
    elif args.kind == "radial":
        from picqa.viz.uniformity_plot import plot_radial_dependence
        df = pd.read_csv(args.input)
        if not args.metric:
            print("--metric required for radial plot", file=sys.stderr)
            return 2
        plot_radial_dependence(df, args.metric, out)
    elif args.kind == "center_vs_edge":
        from picqa.viz.uniformity_plot import plot_center_vs_edge
        df = pd.read_csv(args.input)
        # metric is comma-separated list of columns
        metrics = [args.metric] if args.metric else \
            ["FSR_nm", "PeakIL_near_1310_dB", "I_at_-1V_pA"]
        if args.metric and "," in args.metric:
            metrics = [m.strip() for m in args.metric.split(",")]
        plot_center_vs_edge(df, metrics, out)
    elif args.kind == "vpi":
        from picqa.viz.uniformity_plot import plot_vpi_distribution
        df = pd.read_csv(args.input)
        plot_vpi_distribution(df, out)
    elif args.kind == "vphi":
        # Need raw measurement, not CSV
        from picqa.viz.uniformity_plot import plot_vphi_curve
        measurements = parse_directory(args.input, test_site="DCM_LMZO")
        # Pick a representative working die: first one with valid IV
        target = None
        for m in measurements:
            if m.iv is not None and m.sweeps:
                # Sanity check: leakage at -1V should be > 1nA (working contact)
                if abs(m.iv.at(-1.0)) > 1e-9:
                    target = m
                    break
        if target is None:
            print("No working die found for V-phi plot", file=sys.stderr)
            return 2
        plot_vphi_curve(target, out)
    else:
        print(f"Unknown plot kind: {args.kind}", file=sys.stderr)
        return 2

    print(f"Saved → {out}")
    return 0


def cmd_yield(args: argparse.Namespace) -> int:
    df = pd.read_csv(args.features)
    spec = load_spec(args.spec, args.family)
    evaluated = evaluate_yield(df, spec)
    summary = yield_summary(evaluated, group_by=["Wafer"])

    print(summary.to_string(index=False))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        evaluated.to_csv(out, index=False)
        summary_path = out.with_name(out.stem + "_summary.csv")
        summary.to_csv(summary_path, index=False)
        print(f"Per-die → {out}")
        print(f"Summary → {summary_path}")
    return 0


def cmd_uniformity(args: argparse.Namespace) -> int:
    """Project 1: wafer-level uniformity report."""
    from picqa.analysis.wafer_uniformity import (
        center_vs_edge,
        fsr_to_index_variation,
        iv_uniformity,
        per_radius_stats,
    )

    df = pd.read_csv(args.features)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Center vs edge for grating coupler IL (project 1, item 1)
    cve_il = center_vs_edge(df, "PeakIL_near_1310_dB",
                            group_by=["Wafer"])
    cve_il.to_csv(out_dir / "center_vs_edge_il.csv", index=False)

    # 2. FSR variation (project 1, item 2)
    fsr_var = fsr_to_index_variation(df, group_by=["Wafer", "Session"])
    fsr_var.to_csv(out_dir / "fsr_index_variation.csv", index=False)

    # 3. IV uniformity (project 1, item 3)
    iv_uni = iv_uniformity(df, metric="I_at_-1V_pA",
                           group_by=["Wafer", "Session"])
    iv_uni.to_csv(out_dir / "iv_uniformity.csv", index=False)

    # 4. Per-radius FSR stats
    rad_stats = per_radius_stats(df, "FSR_nm", group_by=["Wafer"])
    rad_stats.to_csv(out_dir / "fsr_per_radius.csv", index=False)

    print("Center vs edge IL:")
    print(cve_il.to_string(index=False))
    print("\nFSR / index variation:")
    print(fsr_var.to_string(index=False))
    print("\nIV uniformity (per session):")
    print(iv_uni.to_string(index=False))
    print(f"\nAll CSVs saved to {out_dir}")
    return 0


def cmd_phase(args: argparse.Namespace) -> int:
    """Project 2: extract V-phi metrics (Vπ, Vπ·L, ER)."""
    from picqa.analysis.phase_extraction import extract_phase_features
    from picqa.extract.mzm import extract_mzm_features
    from picqa.analysis.outlier import flag_failed_contacts

    measurements = parse_directory(args.data_dir, test_site="DCM_LMZO")
    base = extract_mzm_features(measurements)
    base = flag_failed_contacts(base)
    augmented = extract_phase_features(measurements, base)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        augmented.to_csv(out, index=False)
        print(f"Saved {len(augmented)} rows → {out}")
        # Quick console summary
        working = augmented[~augmented["FailedContact"]]
        if not working.empty:
            print(f"\nVπ summary (working dies, n={len(working)}):")
            print(working.groupby("Wafer")["Vpi_V"].describe()
                  [["count", "mean", "50%", "std"]].to_string())
    else:
        print(augmented.head(15).to_string(index=False))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    spec = None
    if args.spec and args.family:
        spec = load_spec(args.spec, args.family)
    md = generate_report(args.data_dir, args.output_dir, spec=spec)
    print(f"Report → {md}")
    return 0


# --------------------------------------------------------------------- #
# Argparse setup
# --------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="picqa",
        description="Photonic IC Quality Analyzer",
    )
    p.add_argument("-V", "--version", action="version", version=f"picqa {__version__}")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="enable INFO logging")
    sub = p.add_subparsers(dest="command", required=True)

    # inventory
    sp = sub.add_parser("inventory", help="summarise files under a data directory")
    sp.add_argument("data_dir")
    sp.set_defaults(func=cmd_inventory)

    # parse
    sp = sub.add_parser("parse", help="parse XMLs to a pickle of Measurements")
    sp.add_argument("data_dir")
    sp.add_argument("--test-site", default=None,
                    help="filter by test site (e.g. DCM_LMZO)")
    sp.add_argument("--output", "-o", default=None)
    sp.set_defaults(func=cmd_parse)

    # extract
    sp = sub.add_parser("extract", help="extract device features to CSV")
    sp.add_argument("device", choices=["mzm", "pd", "pn"])
    sp.add_argument("data_dir")
    sp.add_argument("--output", "-o", default=None)
    sp.set_defaults(func=cmd_extract)

    # plot
    sp = sub.add_parser("plot", help="generate a figure")
    sp.add_argument("kind",
                    choices=["iv", "spectra", "wafermap", "summary",
                             "pn_length", "pn_summary",
                             "radial", "center_vs_edge", "vpi", "vphi"])
    sp.add_argument("input", help="data directory or features CSV depending on kind")
    sp.add_argument("--output", "-o", required=True)
    sp.add_argument("--bias", type=float, default=-2.0,
                    help="DC bias for spectra plot (default: -2.0 V)")
    sp.add_argument("--metric", default=None,
                    help="metric column for wafermap/radial/center_vs_edge plots")
    sp.set_defaults(func=cmd_plot)

    # yield
    sp = sub.add_parser("yield", help="apply spec and compute yield")
    sp.add_argument("features", help="features CSV from `picqa extract`")
    sp.add_argument("--spec", required=True)
    sp.add_argument("--family", required=True, help="spec family name (e.g. mzm)")
    sp.add_argument("--output", "-o", default=None)
    sp.set_defaults(func=cmd_yield)

    # report
    sp = sub.add_parser("report", help="generate a Markdown report")
    sp.add_argument("data_dir")
    sp.add_argument("--output-dir", "-o", required=True)
    sp.add_argument("--spec", default=None,
                    help="optional spec YAML for yield evaluation")
    sp.add_argument("--family", default=None,
                    help="spec family name (required if --spec given)")
    sp.set_defaults(func=cmd_report)

    # uniformity (project 1)
    sp = sub.add_parser("uniformity",
                        help="wafer-level uniformity analysis (project 1)")
    sp.add_argument("features", help="MZM features CSV from `picqa extract mzm`")
    sp.add_argument("--output-dir", "-o", required=True)
    sp.set_defaults(func=cmd_uniformity)

    # phase (project 2)
    sp = sub.add_parser("phase",
                        help="V-phi extraction: Vπ, Vπ·L, ER (project 2)")
    sp.add_argument("data_dir")
    sp.add_argument("--output", "-o", default=None)
    sp.set_defaults(func=cmd_phase)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
