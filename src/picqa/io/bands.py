"""Telecom band classification utilities.

Maps a wavelength (in nm) to its ITU telecom band label, and infers the
band from common test-site / device-name conventions when the explicit
wavelength is missing.

Bands (ITU-T G.692):
* O: 1260 – 1360 nm  (Original)
* E: 1360 – 1460 nm  (Extended)
* S: 1460 – 1530 nm  (Short-wavelength)
* C: 1530 – 1565 nm  (Conventional)
* L: 1565 – 1625 nm  (Long-wavelength)
* U: 1625 – 1675 nm  (Ultra-long-wavelength)
"""

from __future__ import annotations

# Inclusive lower, exclusive upper, except the last band.
_BANDS: list[tuple[str, float, float]] = [
    ("O", 1260.0, 1360.0),
    ("E", 1360.0, 1460.0),
    ("S", 1460.0, 1530.0),
    ("C", 1530.0, 1565.0),
    ("L", 1565.0, 1625.0),
    ("U", 1625.0, 1675.0),
]


def band_from_wavelength(wavelength_nm: float | None) -> str:
    """Return the ITU band label for ``wavelength_nm``, or ``""`` if unknown."""
    if wavelength_nm is None:
        return ""
    try:
        wl = float(wavelength_nm)
    except (TypeError, ValueError):
        return ""
    for label, lo, hi in _BANDS:
        if lo <= wl < hi:
            return label
    # Catch the U-band upper edge inclusively
    if wl == _BANDS[-1][2]:
        return _BANDS[-1][0]
    return ""


def band_from_name(name: str) -> str:
    """Best-effort band inference from a test-site or device name.

    The HY202103 maskset uses naming where the letter immediately after
    ``LMZ`` (Mach-Zehnder), ``PSL`` (PN segment line), or ``M12``/``M22``
    (MMI) indicates the band:

    * ``LMZO``, ``MZMOTE``, ``PSLOTE`` → O-band
    * ``LMZC``, ``MZMCTE``, ``PSLCTE`` → C-band

    Returns ``""`` when no convention matches. The matcher is intentionally
    conservative: it only fires on known prefixes so unrelated names (e.g.
    ``ALIGN_WAFER_CTE``) don't get mislabelled.
    """
    if not name:
        return ""
    upper = name.upper()
    for prefix in ("LMZ", "MZM", "PSL"):
        idx = upper.find(prefix)
        if idx != -1 and len(upper) > idx + len(prefix):
            letter = upper[idx + len(prefix)]
            if letter in {"O", "E", "S", "C", "L", "U"}:
                return letter
    return ""


def band_for_measurement(
    *,
    design_wavelength_nm: float | None,
    test_site: str,
    device_name: str,
) -> str:
    """Combined band lookup, preferring the explicit wavelength.

    1. If ``design_wavelength_nm`` is known, use :func:`band_from_wavelength`.
    2. Otherwise, try test-site naming.
    3. Otherwise, try device-name naming.
    4. Otherwise return ``""``.
    """
    by_wl = band_from_wavelength(design_wavelength_nm)
    if by_wl:
        return by_wl
    by_ts = band_from_name(test_site)
    if by_ts:
        return by_ts
    return band_from_name(device_name)


# Default operating wavelengths used by the HY202103 maskset, by band.
# Used as a fallback when no explicit ``WL`` is in the XML — for example,
# PN modulator files don't include one but their device name still carries
# the band letter.
_DEFAULT_WAVELENGTH_BY_BAND: dict[str, float] = {
    "O": 1310.0,
    "E": 1410.0,
    "S": 1490.0,
    "C": 1550.0,
    "L": 1590.0,
    "U": 1640.0,
}


def default_wavelength_for_band(band: str) -> float | None:
    """Return a representative wavelength for a named band, or ``None``."""
    return _DEFAULT_WAVELENGTH_BY_BAND.get(band.upper())
