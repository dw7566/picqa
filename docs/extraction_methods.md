# Feature extraction methods

This document describes how each metric in the MZM feature DataFrame is
computed, so reviewers and downstream users can reproduce or critique the
choices.

## Free spectral range (`FSR_nm`)

1. Take the 0V wavelength sweep.
2. Run `scipy.signal.find_peaks(-IL, prominence=8 dB)` to locate notches
   (transmission minima are peaks of the negated trace).
3. `FSR = median(diff(notch_wavelengths))`.

If fewer than two notches are detected, `FSR` is NaN.

## Reference notch (`Notch_at_0V_nm`)

The notch closest to the design wavelength of 1310 nm in the 0V sweep.
Used as the seed for tuning-slope tracking.

## Tuning efficiency (`dLambda_dV_pm_per_V`)

For each sweep at biases `[-2, -1.5, -1, -0.5, 0, +0.5]` V:

1. Find all notches in that sweep.
2. Pick the notch closest to the previously tracked wavelength (start with
   the 0V reference).
3. If the closest notch is more than half an FSR away, we assume the
   tracker lost the resonance and skip the point.
4. Linearly fit `wavelength = a · bias + b`. The slope `a` (converted to
   pm/V) is the result.

A minimum of three valid points is required; otherwise `NaN`.

## Peak insertion loss near design wavelength (`PeakIL_near_1310_dB`)

We want the upper envelope of the spectrum near 1310 nm — i.e. the loss
*between* the modulator's notches, which approximates the grating-coupler
peak coupling loss times two.

1. Restrict to wavelengths in `[1310 ± 4 nm]`.
2. Take the 95th percentile of `IL[dB]` in that window.

The 95th percentile is robust against accidental notch overlap with the
1310 nm point.

## Leakage currents (`I_at_-1V_pA`, `I_at_-2V_pA`)

The IV sweep contains 13 points across `[-2, +1]` V. We pick the closest
sweep point to the target voltage and report the current in picoamps.

## Failed-contact flag (`FailedContact`)

The MZM features pipeline marks a die as a failed-contact measurement if
**either**:

- `|dLambda_dV_pm_per_V| < 30 pm/V` (modulator does not respond to bias)
- `|I_at_-1V_pA| < 1000 pA` (SMU reads at noise floor)

Both thresholds are configurable via `flag_failed_contacts()` keyword
arguments.

## Photodetector dark current

Pure IV: `I` at `-1V` and `-2V`, in pA. No averaging, no fitting.

## Why these particular metrics?

For an MZM, four metrics together form a sufficient process-monitoring
fingerprint:
- **FSR** — geometric uniformity of the long arm (sets the modulator's
  free spectral range).
- **Tuning slope** — efficiency of the carrier-depletion phase shifter.
- **Peak IL** — grating coupler quality (dominant contribution to total IL).
- **Leakage** — junction quality.

Combined with the failed-contact flag, this gives a one-row-per-die summary
that supports per-wafer yield, wafer maps, and trend analysis without
storing the full ~6000-point spectra.
