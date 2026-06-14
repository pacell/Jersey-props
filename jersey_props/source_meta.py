"""Pull an image and precise coordinates from a property's listing page.

Estate-agent / portal listing pages (OnTheMarket, Livingroom, Broadlands, ...)
embed an og:image and the property's lat/lng in the HTML. Fetching the listing
once gives us a real photo and an accurate map pin -- far better than a parish
centroid. PDFs / Issuu / pages that block us simply return empty.
"""

from __future__ import annotations

import re

from .http import fetch

# Jersey bounding box for sanity-checking any coords we scrape.
_LAT = (49.15, 49.27)
_LNG = (-2.27, -2.00)

_OG_RE = re.compile(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]*'
                    r'content=["\']([^"\']+)["\']', re.I)
_OG_RE2 = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*'
                     r'(?:property|name)=["\']og:image["\']', re.I)
_LAT_RE = re.compile(r'"lat(?:itude)?"\s*:\s*"?(-?\d{2}\.\d{3,})', re.I)
_LNG_RE = re.compile(r'"(?:lng|lon|longitude)"\s*:\s*"?(-?\d\.\d{3,})', re.I)


def _first_in(matches, lo, hi):
    for m in matches:
        try:
            v = float(m)
        except ValueError:
            continue
        if lo <= v <= hi:
            return round(v, 6)
    return None


def listing_meta(url: str) -> dict:
    """Return {image, lat, lng} scraped from a listing page (any may be absent)."""
    out: dict = {}
    if not url or url.lower().endswith(".pdf"):
        return out
    # Short timeout, no retries -- a slow/dead listing page must not stall the build.
    html = fetch(url, timeout=12, retries=1)
    if not html:
        return out
    m = _OG_RE.search(html) or _OG_RE2.search(html)
    if m:
        img = m.group(1).strip()
        if img.startswith("http"):
            out["image"] = img
    lat = _first_in(_LAT_RE.findall(html), *_LAT)
    lng = _first_in(_LNG_RE.findall(html), *_LNG)
    if lat is not None and lng is not None:
        out["lat"], out["lng"] = lat, lng
    return out
