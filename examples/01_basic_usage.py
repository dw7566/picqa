"""Basic library usage: parse one file, extract features, plot one figure.

Run from the project root::

    python examples/01_basic_usage.py path/to/HY202103
"""

from __future__ import annotations

import sys
from pathlib import Path

from picqa.extract.mzm import extract_mzm_features
from picqa.io.xml_parser import parse_directory
from picqa.viz.spectrum_plot import plot_spectra_grid


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python 01_basic_usage.py <data-dir>", file=sys.stderr)
        return 1
    data_dir = Path(sys.argv[1])

    # 1) Parse all MZM files
    measurements = parse_directory(data_dir, test_site="DCM_LMZO")
    print(f"Parsed {len(measurements)} measurements")

    # 2) Extract MZM features into a DataFrame
    features = extract_mzm_features(measurements)
    print(f"Features:\n{features.head()}")

    # 3) Plot transmission spectra at -2V
    out_png = Path("./out_spectra.png")
    plot_spectra_grid(measurements, out_png, bias_v=-2.0)
    print(f"Saved figure → {out_png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
