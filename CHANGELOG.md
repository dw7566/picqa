# Changelog

## [0.3.0] — Multi-device extraction
- `extract/photodetector.py` — Ge PD dark current
- `extract/waveguide.py` — cut-back loss extractor stub
- `picqa extract pd` CLI subcommand

## [0.2.0] — MZM extraction
- `extract/mzm.py` — FSR, tuning slope, peak IL, leakage
- `picqa extract mzm` CLI subcommand
- Unit tests for MZM extraction

## [0.1.0] — Foundations
- `pyproject.toml`, CI workflow, license, gitignore
- `io/schemas.py` — typed data containers
- `io/xml_parser.py` — XML parser with inventory helper
- Initial unit tests for the IO layer
