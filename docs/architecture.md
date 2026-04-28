# Architecture

## Design principles

picqa is built around a one-way data flow:

```
XML file → Measurement → Features (DataFrame) → Analysis → Figures + Report
   io/       schemas        extract/             analysis/    viz/ + report/
```

Each stage is a separate subpackage. The arrow is one-way: the parser does
not know about features, the extractor does not know about plotting. This
makes every stage testable in isolation and replaceable without touching
the rest of the codebase.

## Module responsibilities

### `io/`
- **`schemas.py`** — Plain dataclasses (`Measurement`, `IVMeasurement`,
  `WavelengthSweep`). No external dependencies beyond NumPy. These types
  are the *contract* between the parser and everyone else.
- **`xml_parser.py`** — Walks one XML file or an entire directory and
  produces lists of `Measurement` objects. Robust to corrupt files (logs
  a warning and skips). Provides an `inventory()` helper for fast file
  counting without full parsing.

### `extract/`
Each module takes a list of `Measurement` and returns a `pandas.DataFrame`.
Adding a new device type means adding one file. The DataFrame contract is
flat (no nested structures) so downstream code can work with arbitrary
pandas operations.

- **`mzm.py`** — MZ modulator features (FSR, tuning slope, peak IL, leakage).
- **`photodetector.py`** — Ge PD dark current.
- **`waveguide.py`** — Cut-back propagation loss (stub).

### `analysis/`
- **`statistics.py`** — Robust median/MAD-based summaries, optionally grouped.
- **`yield_calc.py`** — Spec object loaded from YAML; evaluates pass/fail
  and produces grouped yield summaries.
- **`outlier.py`** — Heuristic detection of failed-contact measurements.

### `viz/`
Each function takes data + an output path, writes a PNG, returns the path.
Functions never display interactively (`matplotlib.pyplot.close` is always
called). This keeps them safe for headless CI environments.

### `report/`
- **`markdown.py`** — Composes inventory, features, stats, yield, and
  figures into a single `report.md`. Uses the other subpackages but is not
  used by them.

### `cli.py`
Argparse-based CLI. Subcommands map 1:1 to library functions; the CLI
itself contains no business logic.

## Why this shape?

1. **Easy to extend.** Adding a new device type touches one file in
   `extract/` and possibly one panel in `viz/`. Nothing else changes.
2. **Easy to test.** Each module has a small, well-defined surface;
   fixtures need only be built once.
3. **Easy to script.** Anyone can write `from picqa.extract.mzm import …`
   without dragging in plotting or CLI dependencies.
4. **Easy to replace.** If an XML format changes, only `io/xml_parser.py`
   needs updating; the dataclasses can stay the same.

## Dependency map

```
        cli.py
          │
     ┌────┼─────────┬────────────┐
     │    │         │            │
   io/  extract/  analysis/   viz/    report/
     │    │ ▲       │ ▲        │ ▲      │
     │    │ │       │ │        │ │      │
     └────┘ └───────┘ └────────┘ │      │
                                 │      │
                       (uses io, extract, analysis, viz)
```

`io` has no internal dependencies.
`extract`, `analysis`, `viz` depend only on `io`.
`report` depends on everything; nothing depends on `report`.

This DAG is enforced by convention; consider adding `import-linter` if it
ever becomes a problem.
