# PN modulator (PCM_PSLOTE_P1N1) analysis

This page documents how picqa analyses PN modulator test sites and what
metrics it produces.

## Test site layout

A `PCM_PSLOTE_P1N1` XML file contains one `ModulatorSite` with a `Modulator`
block holding **four PortCombo entries**:

| PortCombo | Role | Length | What it has |
|---|---|---|---|
| 0 (REF) | Reference waveguide | n/a | One 0 V optical sweep, no IV |
| 1, 2, 3 | Active PN segments | 500, 1500, 2500 µm | IV + 6 wavelength sweeps each |

The reference port serves as a baseline for back-out: subtracting its
insertion loss from each active segment's IL leaves the contribution of the
PN doping itself (`IL_drop_vs_REF_dB`).

## Why the metrics differ from MZM

A Mach-Zehnder modulator is an interferometer, so its transmission spectrum
shows periodic notches whose wavelengths shift with bias. Tuning efficiency
is naturally measured as `dλ/dV`.

A standalone PN-doped waveguide (this test site) has no interferometer.
Its spectrum is roughly monotonic. Modulation happens through carrier-induced
**electroabsorption**: the IL at a fixed wavelength changes with bias as the
free-carrier population in the waveguide changes. The natural metric is
therefore `dIL/dV` at the design wavelength (1310 nm).

## Per-segment metrics (`pn_segments.csv`)

One row per (die, segment_length).

| Column | Meaning | Units |
|---|---|---|
| `Length_um` | Active PN segment length | µm |
| `PortLabel` | XML port-pair label such as `IN_1/OUT_1` | — |
| `PeakIL_at_1310_dB` | Insertion loss at 1310 nm in the 0 V sweep | dB |
| `IL_drop_vs_REF_dB` | `PeakIL - reference IL`. Negative numbers indicate that the doped segment is lossier than the bare waveguide | dB |
| `dIL_dV_dB_per_V` | Linear fit of IL @ 1310 nm vs DC bias across all 6 biases | dB/V |
| `I_at_-1V_pA`, `I_at_-2V_pA` | Reverse-bias leakage currents | pA |

## Per-die length-fit metrics (`pn_length_fit.csv`)

One row per die. Linear fits across the three active lengths.

| Column | Meaning | Units |
|---|---|---|
| `Loss_per_um_dB_per_um` | Slope of `IL_drop_vs_REF_dB` vs `Length_um`. The per-µm loss attributable to PN doping. Multiply by 10⁴ for dB/cm | dB/µm |
| `Loss_intercept_dB` | y-intercept of the same fit (loss at length=0). Should be near 0 if the reference subtraction worked | dB |
| `Loss_R2` | R² of the loss fit. Values near 1 indicate clean linear scaling | — |
| `Modulation_per_um_dB_per_V_per_um` | Slope of `dIL_dV_dB_per_V` vs length. The per-µm electroabsorption efficiency. Multiply by 10³ for dB/V/mm | dB/V/µm |
| `Modulation_intercept_dB_per_V` | y-intercept of the modulation fit | dB/V |
| `Modulation_R2` | R² of the modulation fit | — |

## Why fit against length

The per-µm slopes are the only metrics that describe the **PN-doped waveguide
itself** and not the rest of the test structure. The intercepts absorb
everything length-independent (coupler loss, fixed offsets, measurement
artefacts), so they don't pollute the per-µm number.

This is the same idea as the cut-back method for waveguide loss extraction.
It works cleanly here because we have three lengths in geometric progression
(500, 1500, 2500 µm), giving a wide enough dynamic range for the fit to be
well-conditioned.

## Failed-contact detection

The PN extractor doesn't include an explicit `FailedContact` flag yet. Use
the modulation efficiency directly: a working die typically shows
|Modulation_per_um| above 5×10⁻⁶ dB/V/µm (~5 mdB/V/cm). Sessions where the
probe lost contact return values around zero, which is what `viz.pn_summary`
filters out for its boxplots.

## CLI

```bash
# Extract per-segment + per-die fit CSVs
picqa extract pn /path/to/HY202103 -o ./out/pn_segments.csv

# Length-dependence scatter (one line per die, mean overlay per wafer)
picqa plot pn_length ./out/pn_segments.csv -o ./out/pn_length.png

# Three-panel summary (loss, modulation, trade-off)
picqa plot pn_summary ./out/pn_segments_lengthfit.csv -o ./out/pn_summary.png
```

The integrated `picqa report` command runs PN analysis automatically when PN
files are present, producing `pn_segments.csv`, `pn_length_fit.csv`, and
both PN figures alongside the MZM outputs.

## Library

```python
from picqa.io.pn_parser import parse_pn_directory
from picqa.extract.pn_modulator import (
    extract_pn_segment_features,
    extract_pn_length_fit,
)

measurements = parse_pn_directory("./HY202103")
seg = extract_pn_segment_features(measurements)
fit = extract_pn_length_fit(seg)

print(fit.groupby("Wafer")["Loss_per_um_dB_per_um"].median() * 1e4)
# Doping loss in dB/cm per wafer
```
