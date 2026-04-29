"""Optical spectrum plots."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from picqa.io.schemas import Measurement


def plot_spectra_grid(
    measurements: list[Measurement],
    output_path: str | Path,
    *,
    test_site: str = "DCM_LMZO",
    bias_v: float = -2.0,
    title: str | None = None,
    ncols: int = 3,
    xlim: tuple[float, float] = (1280, 1340),
    ylim: tuple[float, float] = (-50, 0),
) -> Path:
    """Overlay all dies' spectra at a fixed bias, one panel per wafer-session."""
    sel = [m for m in measurements if m.test_site == test_site]
    if not sel:
        raise ValueError(f"No measurements for test_site={test_site}")

    groups = sorted({(m.wafer, m.session) for m in sel})
    nrows = (len(groups) + ncols - 1) // ncols
    fig = plt.figure(figsize=(4.3 * ncols, 3.4 * nrows))

    for i, (w, s) in enumerate(groups):
        ax = fig.add_subplot(nrows, ncols, i + 1)
        for m in [x for x in sel if x.wafer == w and x.session == s]:
            sw = m.sweep_at_bias(bias_v)
            if sw is None:
                continue
            ax.plot(sw.wavelength_nm, sw.insertion_loss_db, alpha=0.4, lw=0.5)
        ax.set_title(f"{w} / {s}", fontsize=9)
        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel("IL (dB)")
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.grid(True, alpha=0.3)

    if title is None:
        title = f"Transmission spectra @ DC bias = {bias_v:+.1f} V"
    fig.suptitle(title, fontsize=12, y=1.0)
    fig.tight_layout()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_bias_shift(
    measurement: Measurement,
    output_path: str | Path,
    *,
    zoom_window_nm: tuple[float, float] | None = None,
    full_window_nm: tuple[float, float] | None = None,
) -> Path:
    """Plot all biases of one die, full range and zoomed near design wavelength.

    If ``full_window_nm`` or ``zoom_window_nm`` is ``None``, sensible defaults
    are derived from the measurement's own ``design_wavelength_nm`` so the
    same call works for O-band (1310 nm) and C-band (1550 nm) devices.
    """
    if not measurement.sweeps:
        raise ValueError("Measurement has no wavelength sweeps")

    sweeps = sorted(measurement.sweeps, key=lambda s: s.dc_bias_v)

    # Derive plot ranges
    design_wl = measurement.design_wavelength_nm or 1310.0
    if full_window_nm is None:
        # ±30 nm around the design wavelength is wide enough to show
        # several FSRs in either band.
        full_window_nm = (design_wl - 30.0, design_wl + 30.0)
    if zoom_window_nm is None:
        # ±5 nm is enough to see one notch in detail.
        zoom_window_nm = (design_wl - 5.0, design_wl + 5.0)

    # Snap windows to the actual measured range so we don't draw an empty
    # left or right margin if the sweep is narrower than ±30 nm.
    all_L = sweeps[0].wavelength_nm
    L_min, L_max = float(all_L.min()), float(all_L.max())
    full_window_nm = (max(full_window_nm[0], L_min),
                      min(full_window_nm[1], L_max))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

    for sw in sweeps:
        axes[0].plot(sw.wavelength_nm, sw.insertion_loss_db, lw=0.6,
                     label=f"{sw.dc_bias_v:+.1f} V")
    axes[0].set_xlim(*full_window_nm)
    axes[0].set_ylim(-50, 0)
    axes[0].set_xlabel("Wavelength (nm)")
    axes[0].set_ylabel("IL (dB)")
    band_str = f" ({measurement.band}-band)" if measurement.band else ""
    axes[0].set_title(
        f"Bias-dependent spectra: {measurement.wafer}/{measurement.die}{band_str}"
    )
    axes[0].legend(loc="lower left", ncol=2, fontsize=8)
    axes[0].grid(alpha=0.3)

    lo, hi = zoom_window_nm
    for sw in sweeps:
        m = (sw.wavelength_nm >= lo) & (sw.wavelength_nm <= hi)
        axes[1].plot(sw.wavelength_nm[m], sw.insertion_loss_db[m], lw=0.8,
                     label=f"{sw.dc_bias_v:+.1f} V")
    axes[1].set_xlabel("Wavelength (nm)")
    axes[1].set_ylabel("IL (dB)")
    axes[1].set_title(f"Zoom near design wavelength ({design_wl:.0f} nm)")
    axes[1].legend(loc="lower left", ncol=2, fontsize=8)
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out
