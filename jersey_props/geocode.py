"""Approximate geocoding for the map overlay.

Jersey road-level geocoding is unreliable (OSM barely maps the lanes), so we
place each property at its parish centroid plus a small deterministic jitter so
markers in the same parish don't stack. A few well-known localities get a better
fixed position. Good enough for a personal "what sold near here" map; positions
are approximate, not surveyed.
"""

from __future__ import annotations

import hashlib

# Approx parish centroids (lat, lng).
PARISH_CENTROIDS = {
    "st. helier": (49.1860, -2.1060),
    "st. saviour": (49.1960, -2.0830),
    "st. clement": (49.1780, -2.0580),
    "grouville": (49.1870, -2.0410),
    "st. martin": (49.2140, -2.0400),
    "trinity": (49.2240, -2.0780),
    "st. john": (49.2430, -2.1100),
    "st. mary": (49.2360, -2.1350),
    "st. ouen": (49.2220, -2.1720),
    "st. peter": (49.2070, -2.1500),
    "st. brelade": (49.1830, -2.1900),
    "st. lawrence": (49.2050, -2.1180),
}

# Distinctive locality keywords -> better fixed coords (checked before parish).
LOCALITIES = {
    "st aubin": (49.1874, -2.1705), "st. aubin": (49.1874, -2.1705),
    "gorey": (49.1985, -2.0218),
    "rozel": (49.2360, -2.0420),
    "bouley bay": (49.2400, -2.0760),
    "bonne nuit": (49.2470, -2.1230),
    "ouaisne": (49.1820, -2.1830), "ouaisné": (49.1820, -2.1830),
    "beaumont": (49.1880, -2.1470),
    "gorey village": (49.1985, -2.0218),
    "st brelade's bay": (49.1790, -2.2010), "st. brelade's bay": (49.1790, -2.2010),
    "corbiere": (49.1820, -2.2470),
    "grève de lecq": (49.2540, -2.1500), "greve de lecq": (49.2540, -2.1500),
}

_DEFAULT = (49.2100, -2.1300)  # island centre


def _jitter(seed: str, span: float = 0.012) -> tuple[float, float]:
    """Deterministic small offset (~±0.7km) from a stable hash of the name."""
    h = hashlib.md5(seed.encode("utf-8")).hexdigest()
    dx = (int(h[:8], 16) / 0xFFFFFFFF - 0.5) * span
    dy = (int(h[8:16], 16) / 0xFFFFFFFF - 0.5) * span
    return dx, dy


def coords_for(parish: str, name: str, address: str = "") -> tuple[float, float]:
    blob = f"{name} {address}".lower()
    base = None
    for kw, pt in LOCALITIES.items():
        if kw in blob:
            base = pt
            break
    if base is None:
        base = PARISH_CENTROIDS.get((parish or "").strip().lower(), _DEFAULT)
    dx, dy = _jitter(name or address or parish or "x")
    return round(base[0] + dx, 6), round(base[1] + dy, 6)
