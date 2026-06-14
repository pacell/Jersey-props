"""Best-effort extraction of key metrics from a brochure / listing page.

Brochures live on many hosts (agent sites, Issuu, Savills PDFs). We fetch the
first HTML URL we can and regex out size / bedrooms / acres / sea-view. PDFs and
JS-only pages won't yield much; we also mine any free-text `notes` we already
have. Nothing raises -- missing metrics just stay empty.
"""

from __future__ import annotations

import html as html_mod
import re

from .http import fetch

_SQFT_RE = re.compile(r"([\d,]{3,})\s*(?:sq\.?\s*ft|square\s*f(?:ee|oo)t|sqft)", re.I)
_SQM_RE = re.compile(r"([\d,]{2,})\s*(?:sq\.?\s*m|square\s*met)", re.I)
_BED_RE = re.compile(r"(\d{1,2})\s*(?:bed|bedroom)", re.I)
_BATH_RE = re.compile(r"(\d{1,2})\s*(?:bath|bathroom)", re.I)
_ACRE_RE = re.compile(r"([\d.]+)\s*acre", re.I)
_SEA_RE = re.compile(r"sea view|sea-view|coastal|seafront|beach|bay|ocean|"
                     r"waterfront|harbour view|cliff", re.I)
# what3words address, e.g. ///filled.count.soap (require the /// marker)
_W3W_RE = re.compile(r"///\s*([a-z]{3,}\.[a-z]{3,}\.[a-z]{3,})", re.I)

# Plausible floor-area bounds (sq ft) -- reject phone numbers / prices / typos.
_MIN_SQFT, _MAX_SQFT = 300, 60_000


def _clean(text: str) -> str:
    text = html_mod.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def metrics_from_text(text: str) -> dict:
    """Extract metrics from any plain-ish text blob (page body or notes)."""
    t = _clean(text)
    out: dict = {}
    for m in _SQFT_RE.finditer(t):
        v = int(m.group(1).replace(",", ""))
        if _MIN_SQFT <= v <= _MAX_SQFT:
            out["size_sqft"] = v
            break
    if "size_sqft" not in out:
        for m in _SQM_RE.finditer(t):
            v = round(int(m.group(1).replace(",", "")) * 10.7639)
            if _MIN_SQFT <= v <= _MAX_SQFT:
                out["size_sqft"] = v
                out["size_note"] = "converted from sq m"
                break
    if (m := _W3W_RE.search(t)):
        out["what3words"] = m.group(1).lower()
    if (m := _BED_RE.search(t)):
        out["bedrooms"] = int(m.group(1))
    if (m := _BATH_RE.search(t)):
        out["bathrooms"] = int(m.group(1))
    if (m := _ACRE_RE.search(t)):
        out["acres"] = float(m.group(1))
    if _SEA_RE.search(t):
        out["sea_view"] = True
    return out


def fetch_metrics(urls, notes: str = "") -> dict:
    """Try each brochure URL (HTML only) then notes; merge what we find."""
    merged: dict = {}
    for url in (urls or []):
        if url.lower().endswith(".pdf") or "issuu.com" in url.lower():
            continue  # not HTML-parseable here
        html = fetch(url)
        if html:
            for k, v in metrics_from_text(html).items():
                merged.setdefault(k, v)
    for k, v in metrics_from_text(notes).items():
        merged.setdefault(k, v)
    return merged
