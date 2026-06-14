"""Approximate geocoding for the map overlay.

Jersey road-level geocoding is unreliable (OSM barely maps the lanes), so we
place each property at its parish centroid plus a small deterministic jitter so
markers in the same parish don't stack. A few well-known localities get a better
fixed position. Good enough for a personal "what sold near here" map; positions
are approximate, not surveyed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

from . import config

# Nominatim (OpenStreetMap) for real street-level coords where it resolves.
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_NOM_UA = "jersey-props-personal/1.0 (https://github.com/pacell/jersey-props)"
_CACHE_PATH = os.path.join(config.DATA_DIR, "geocode_cache.json")
# Jersey bounding box -- reject anything that resolves elsewhere.
_BOUNDS = (49.15, 49.27, -2.27, -2.00)  # lat_min, lat_max, lng_min, lng_max
_ROAD_RE = re.compile(
    r"\b(rue|route|mont|chemin|avenue|lane|clos|ruette|esplanade|street|road|"
    r"hill|chasse|colomberie|gardens|close|place|grande|petite)\b", re.I)

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


_cache: dict | None = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def save_cache() -> None:
    if _cache is not None:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f)


def _in_bounds(lat: float, lng: float) -> bool:
    return _BOUNDS[0] <= lat <= _BOUNDS[1] and _BOUNDS[2] <= lng <= _BOUNDS[3]


def _nominatim(query: str) -> tuple[float, float] | None:
    """Query Nominatim once (cached, rate-limited). Returns coords or None."""
    cache = _load_cache()
    if query in cache:
        v = cache[query]
        return tuple(v) if v else None
    url = _NOMINATIM + "?" + urllib.parse.urlencode(
        {"format": "json", "limit": 1, "countrycodes": "je", "q": query})
    result = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _NOM_UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if data:
            lat, lng = float(data[0]["lat"]), float(data[0]["lon"])
            if _in_bounds(lat, lng):
                result = (round(lat, 6), round(lng, 6))
    except Exception:  # noqa: BLE001 - never let geocoding break the build
        result = None
    cache[query] = list(result) if result else None
    time.sleep(1.1)  # be polite to Nominatim (max ~1 req/s)
    return result


def _road(address: str, name: str) -> str:
    segs = [s.strip() for s in (address or name).split(",")
            if s.strip() and s.strip() != "—"]
    for s in segs:
        if _ROAD_RE.search(s):
            return s
    return segs[0] if segs else ""


def geocode(parish: str, name: str, address: str = "") -> tuple[float, float]:
    """Best coords for a property: Nominatim road/parish, else parish centroid.

    Tries the road+parish then the parish via Nominatim (cached). Falls back to
    the parish centroid + deterministic jitter when nothing resolves in-island.
    """
    road = _road(address, name)
    queries = []
    if road:
        queries.append(f"{road}, {parish}, Jersey")
    for kw in LOCALITIES:  # try a known locality token if present
        if kw in f"{name} {address}".lower():
            queries.append(f"{kw}, Jersey")
            break
    for q in queries:
        hit = _nominatim(q)
        if hit:
            return hit
    return coords_for(parish, name, address)


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
