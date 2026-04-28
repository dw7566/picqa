# HY202103 data format

## Directory layout

```
HY202103/
  D07/                              # wafer ID
    20190715_190855/                # session timestamp
      HY202103_D07_(0,0)_LION1_DCM_LMZO.xml
      HY202103_D07_(0,0)_LION1_DCM_GPDO.xml
      ...
  D08/
    20190526_082853/
      ...
```

## Filename pattern

```
HY202103_<wafer>_(<col>,<row>)_LION1_<TEST_SITE>.xml
```

- `<wafer>` — wafer ID (e.g. `D08`)
- `<col>,<row>` — die coordinates, integer, can be negative
- `LION1` — maskset name
- `<TEST_SITE>` — test type tag (see below)

## Test site tags

| Tag | Device |
|---|---|
| `DCM_LMZO`        | Mach-Zehnder modulator (carrier-depletion, O-band) |
| `DCM_GPDO`        | Germanium photodetector |
| `DCM_FGCOTE_1DC`  | 1-D grating coupler |
| `DCM_M12OTE`      | Multi-mode interferometer (1×2) |
| `DCM_M22OTE`      | Multi-mode interferometer (2×2) |
| `DCM_LMZC`        | Mach-Zehnder modulator (C-band) |
| `OTEST_L3OTE`     | 3-length waveguide spiral set |
| `OTEST_L4OTE`     | 4-length waveguide spiral set |
| `PCM_DC3OTE_WG`   | Directional coupler (waveguide) |
| `PCM_L_EXPO`      | Long waveguide loss test |
| `PCM_PSLOTE_P1N1` | PN modulator, 1+1 segment |
| `PCM_PSLCTE_P1N1` | PN modulator, C-band |
| `ALIGN_WAFER_CTE` | Wafer-level alignment reference |

## XML structure

Common root element ``OIOMeasurement`` with attributes:
- `CreationDate` — ISO-like timestamp
- `OIOSoftwareVersion` — measurement software version

Top-level children:
- `TestSiteInfo` — Wafer, DieColumn, DieRow, Batch, Maskset, TestSite
- `ElectroOpticalMeasurements` (or similar) — wraps the actual data

Measurement data is contained inside one of:
- `Modulator` — for MZMs and PN modulators
- `WaveguideLossMeasurement` — for spiral test sites
- `DetectorMeasurement` — for photodetectors

Inside the data block:
- `DesignDescription` — free text
- `DeviceInfo/DesignParameter` — geometric parameters with `Symbol`, `Name`, `Unit`
- `IVMeasurement/Voltage`, `IVMeasurement/Current` — comma-separated arrays
- `WavelengthSweep` (one per DC bias) with `<L>` and `<IL>` arrays and a
  `DCBias` attribute
- `AlignWavelength` — wavelength used for alignment

Most arrays are stored as a single comma-separated text string under each
element. picqa parses these via `numpy.fromstring(text, sep=",")`.

## What picqa currently consumes

The MZM extractor (the most complete one) uses:
- `TestSiteInfo` for die identification
- `IVMeasurement` for leakage at fixed biases
- `WavelengthSweep` for FSR, tuning slope, and peak IL

The photodetector extractor reads `IVMeasurement` blocks (dark-current biases)
when present. Note that in the bundled HY202103 dataset the `DCM_GPDO` files
contain only optical `PortLossMeasurement` blocks, so the extractor returns an
empty DataFrame — providing GPDO files with IV traces from another run will
populate it without code changes.

The waveguide module is currently a placeholder — see `extract/waveguide.py`.
