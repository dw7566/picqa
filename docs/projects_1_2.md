# Projects 1 & 2 — Wafer uniformity and V-phi extraction

This page documents the two analyses introduced in v1.2.0.

## Project 1: Wafer-level process variation

Goal: quantify how device performance varies with position on the wafer.

### Implementation

`src/picqa/analysis/wafer_uniformity.py` adds simple but robust spatial
statistics on top of the per-die feature table:

* `add_radius_column` — distance from die (0,0) in die-spacing units
* `add_region_column` — labels "center" vs "edge" with a configurable
  threshold (default 2.5 die-units puts ~6 dies in the center)
* `center_vs_edge` — per-group medians, CVs, and the center-edge delta
  for any metric
* `per_radius_stats` — median + CV at each integer-rounded radius
* `fsr_to_index_variation` — converts FSR scatter into an estimate of
  group-index (and therefore geometry) variation. Rationale: for an
  unbalanced MZI, FSR ≈ λ²/(n_g·ΔL), so σ_FSR/FSR ≈ σ_n_g/n_g
* `iv_uniformity` — mean / std / CV / robust median + MAD for any
  IV-derived column

### CLI

```bash
# Compute all four uniformity tables for a CSV of MZM features
picqa uniformity ./out/features.csv -o ./out/uniformity

# Standalone plots
picqa plot radial ./out/features.csv \
  --metric PeakIL_near_1310_dB -o ./out/radial_il.png

picqa plot center_vs_edge ./out/features.csv \
  --metric "FSR_nm,PeakIL_near_1310_dB,I_at_-1V_pA" \
  -o ./out/center_vs_edge.png
```

The unified `picqa report` command runs uniformity automatically and writes
the three CSVs and two plots into the report directory.

### Findings on the HY202103 dataset

* **Grating coupler IL** is systematically better near the wafer center than
  at the edge by ~1.0–1.9 dB (median), with substantially smaller spread
  (CV ≈ 2–5 % center vs 10–14 % edge). The effect is consistent across
  all three wafers.
* **FSR relative variation** is 0.6 – 0.9 % per session, suggesting that
  waveguide width × thickness is uniform to roughly the same level.
* **IV uniformity** has CV ≈ 10 – 26 % on working sessions, with D24's
  later session being the most uniform.

## Project 2: V–φ characterisation

Goal: extract the standard MZM performance metrics — Vπ, Vπ·L, ER —
automatically from the bias-dependent transmission spectra we already
collect.

### Theory (one paragraph)

Adjacent transmission notches in an MZI are spaced by one FSR in
wavelength and 2π in phase. So tracking how a notch shifts with bias V
gives the phase-vs-voltage relation:

```
Δφ(V) = 2π · (λ_notch(V) − λ_notch(0)) / FSR
Vπ    = FSR / (2 · |dλ/dV|)
```

Vπ·L additionally requires the active phase-shifter length, which is
parsed best-effort from the device name (e.g. `MZMOTE_LULAB_380_500` →
380 µm). When the name doesn't contain a parseable length, Vπ·L is left
as NaN.

The extinction ratio is computed as `IL_max − IL_min` inside a ±5 nm
window centred on the design wavelength.

### Implementation

`src/picqa/analysis/phase_extraction.py` provides:

* `voltage_to_phase(biases, notch_lambdas, fsr)` — vectorised conversion
  to radians, with phase referenced to the bias closest to 0 V
* `vpi_from_slope(slope_nm_per_v, fsr_nm)` — closed-form Vπ
* `parse_phaseshifter_length_um(device_name)` — best-effort length parse
* `extract_phase_features(measurements, mzm_features)` — appends Vπ_V,
  Vπ_L_V_cm, PhaseShifter_Length_um, ER_at_-2V_dB, ER_at_0V_dB columns
  to the existing MZM feature DataFrame
* `vphi_trace(measurement)` — table of (Bias, Notch, Δφ) for plotting

### CLI

```bash
# Extract V-phi metrics for every MZM die
picqa phase ./HY202103 -o ./out/phase_features.csv

# Single-die V-φ curve (auto-picks first working die)
picqa plot vphi ./HY202103 -o ./out/vphi_curve.png

# Per-wafer Vπ distribution + Vπ·L scatter
picqa plot vpi ./out/phase_features.csv -o ./out/vpi_distribution.png
```

Like uniformity, V-phi extraction is automatically included in
`picqa report` output.

### Findings on the HY202103 dataset

| Wafer | Vπ median (V) | Vπ·L median (V·cm) | ER @ -2V (dB) |
|---|---|---|---|
| D08 | 26.7 | 1.02 | ~37 |
| D23 | 36.4 | 1.39 | ~37 |
| D24 | 39.2 | 1.49 | ~37 |

D08 has the lowest Vπ (best modulation efficiency), in line with what the
PN modulator analysis showed for the same wafer (highest doping → highest
modulation per unit length). The Vπ values themselves are characteristic of
an unstrained Si MZM with a sub-mm phase shifter — typical literature values
for such devices are 20–40 V·cm, consistent with what we extract here.
