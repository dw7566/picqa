# Changelog

## [1.2.0] — Projects 1 + 2
- Wafer-level uniformity analysis (center-vs-edge, radial trends, FSR-to-index, IV uniformity)
- V-phi extraction: Vπ, Vπ·L, ER from existing dλ/dV data
- New CLI: `picqa uniformity`, `picqa phase`
- New plot kinds: radial, center_vs_edge, vphi, vpi
- 14 new tests; integrated into unified report (now 11 figures + 11 CSVs)


All notable changes to this project will be documented in this file.

## [1.0.0] — Initial release

- Full module surface (io, extract, analysis, viz, report, cli)
- MZM feature extraction (FSR, tuning slope, peak IL, leakage)
- Photodetector dark current extraction
- Spec-based yield evaluation from YAML
- Failed-contact heuristic
- Five plot types: IV grid, spectra grid, bias-shift, wafer map, summary
- Markdown report generator
- 6 test modules, end-to-end CLI tests

## [0.5.0] — Reporting

- `report/markdown.py` — full Markdown report assembly
- `picqa report` CLI subcommand

## [0.4.0] — Analysis & visualisation

- `analysis/yield_calc.py` with YAML spec loading
- `analysis/statistics.py` robust grouped statistics
- `analysis/outlier.py` failed-contact heuristic
- All `viz/` plot modules

## [0.3.0] — Multi-device extraction

- `extract/photodetector.py`
- `extract/waveguide.py` (stub)

## [0.2.0] — MZM extraction

- `extract/mzm.py` with FSR / tuning slope / peak IL
- `picqa extract mzm` CLI

## [0.1.0] — Foundations

- `pyproject.toml`, CI workflow, license
- `io/schemas.py` data containers
- `io/xml_parser.py` parser + inventory
- `picqa inventory`, `picqa parse` CLI
