# Changelog

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
