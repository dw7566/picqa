# Multi-band support (v1.3.0)

picqa is *band-agnostic*: the same code paths handle any telecom band
(O, E, S, C, L, U) without modification. This page explains how the
detection works and what changes when you scan a multi-band dataset.

## How a band gets attached to a measurement

Three sources are tried in order, first hit wins:

1. **Explicit `WL` design parameter** in the XML
   ```xml
   <DesignParameter Symbol="WL" Name="Design wavelength" Unit="...">1310</DesignParameter>
   ```
   When present (MZM files have it; PN files don't), this is the most
   authoritative source.

2. **Test-site naming convention**, e.g.
   * `DCM_LMZO`, `MZMOTE_*`, `PSLOTE_*` → O-band (1310 nm)
   * `DCM_LMZC`, `MZMCTE_*`, `PSLCTE_*` → C-band (1550 nm)

3. **Device name fallback** (rarely needed) — same letter convention as
   test-site names.

The result is stored on every parsed `Measurement` / `PNMeasurement`:
```python
m.design_wavelength_nm  # float | None
m.band                  # "O" | "C" | "L" | ... | ""
```

## Band-aware extraction

The MZM and PN extractors use the measurement's own design wavelength
internally, so:
* notch search seeds and IL envelopes window around the right peak,
* extinction ratio is computed at the right wavelength, and
* `Vπ = FSR / (2|dλ/dV|)` works for any band as long as FSR and the
  tuning slope are themselves estimated correctly.

Two new columns are added to the feature tables:
* `Band` — single-letter ITU label (`"O"`, `"C"`, ...)
* `DesignWavelength_nm` — the wavelength actually used during extraction

The legacy column `PeakIL_near_1310_dB` is still emitted as an alias of
`PeakIL_dB` for back-compatibility with any scripts written against
v1.2.x output.

## CLI scope expansion

`picqa extract mzm` and `picqa extract pn` now scan **both bands at once**
by passing the relevant test-site lists internally:
```python
MZM_TEST_SITES = ("DCM_LMZO", "DCM_LMZC")
PN_TEST_SITES  = ("PCM_PSLOTE_P1N1", "PCM_PSLCTE_P1N1")
```
You don't need to do anything different — the new `Band` column lets you
filter or group downstream:
```python
import pandas as pd
df = pd.read_csv("features.csv")

oband = df[df.Band == "O"]
cband = df[df.Band == "C"]

print(oband["FSR_nm"].median())   # ~9.83 nm at 1310 nm
print(cband["FSR_nm"].median())   # ~14.3 nm at 1550 nm
```

## Adding a new band

If a new test site is added later (say, `DCM_LMZL` for L-band), it's a
two-line change:
```python
# picqa/extract/mzm.py
MZM_TEST_SITES = ("DCM_LMZO", "DCM_LMZC", "DCM_LMZL")
```
The naming convention in `bands.py` already handles `LMZL` → `L`, and
`default_wavelength_for_band("L")` already returns 1590 nm, so the rest
of the pipeline just works.

## Findings on the HY202103 dataset (now including D07)

| Wafer | Band | n dies | Median FSR | Median \|dλ/dV\| | Median Vπ | Notes |
|---|---|---|---|---|---|---|
| D07 | C | 14 | 14.4 nm | 244 pm/V | 29.2 V | Newly visible after v1.3.0 |
| D08 | C | 14 | 14.2 nm | 240 pm/V | ~28 V | Same wafer as D08-O — direct cross-band comparison |
| D08 | O | 14 | 9.83 nm | 183 pm/V | 27.5 V | |
| D23 | O | 28 | 9.85 nm | 64 pm/V | 36.4 V | |
| D24 | O | 28 | 9.83 nm | 69 pm/V | 39.2 V | |

A few observations the multi-band view enables:

* **FSR scales as expected** — at 1550 nm the FSR is ≈ 14.3 nm vs 9.83 nm
  at 1310 nm. The ratio (1.46×) closely matches what group-index
  considerations predict for the same MZ arm-length difference.
* **D08 cross-band consistency** — Vπ at 1310 nm and 1550 nm are within
  2 V of each other on the same wafer, suggesting that the phase
  shifter's effective modulation strength tracks the carrier-induced
  index change with the expected wavelength dependence.
* **PN modulator wavelength sensitivity** — D07 (C-band) shows a median
  electroabsorption of -0.16 dB/V vs D08 (O-band) -0.12 dB/V at the
  longest segment. Free-carrier absorption scales with λ², so a 1.4×
  ratio is again right in line with theory.
