"""Batch analysis: extract features, apply spec, summarise yield, save report.

Run from the project root::

    python examples/02_batch_analysis.py path/to/HY202103 ./out
"""

from __future__ import annotations

import sys
from pathlib import Path

from picqa.analysis.outlier import flag_failed_contacts
from picqa.analysis.statistics import per_group_stats
from picqa.analysis.yield_calc import evaluate_yield, load_spec, yield_summary
from picqa.extract.mzm import extract_mzm_features
from picqa.io.xml_parser import parse_directory
from picqa.report.markdown import generate_report


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python 02_batch_analysis.py <data-dir> <out-dir>", file=sys.stderr)
        return 1

    data_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Parse + extract
    measurements = parse_directory(data_dir, test_site="DCM_LMZO")
    features = flag_failed_contacts(extract_mzm_features(measurements))
    features.to_csv(out_dir / "features.csv", index=False)

    # 2) Statistics by wafer/session
    stats = per_group_stats(
        features,
        group_by=["Wafer", "Session"],
        metrics=[
            "FSR_nm",
            "Notch_at_0V_nm",
            "dLambda_dV_pm_per_V",
            "PeakIL_near_1310_dB",
            "I_at_-1V_pA",
        ],
    )
    stats.to_csv(out_dir / "stats.csv", index=False)
    print(stats.to_string(index=False))

    # 3) Yield using bundled spec
    spec_path = Path(__file__).resolve().parent.parent / "configs" / "mzm_spec.yaml"
    if spec_path.exists():
        spec = load_spec(spec_path, "mzm")
        evaluated = evaluate_yield(features, spec)
        evaluated.to_csv(out_dir / "yield.csv", index=False)
        summary = yield_summary(evaluated, group_by=["Wafer"])
        summary.to_csv(out_dir / "yield_summary.csv", index=False)
        print("\nYield per wafer:")
        print(summary.to_string(index=False))

        # 4) Markdown report
        generate_report(data_dir, out_dir / "report", spec=spec, measurements=measurements)
    else:
        generate_report(data_dir, out_dir / "report", measurements=measurements)

    print(f"\nAll outputs in: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
