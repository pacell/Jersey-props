"""Wayback Machine (web.archive.org) CDX helpers for the enrichment stage.

These functions talk to the public CDX API documented at
https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server .

IMPORTANT: web.archive.org must be reachable for any of this to return data.
It may be blocked by egress policy in some sandboxes; in that case every
function here degrades gracefully (returns [] / None) instead of raising, so
the pipeline keeps running. Run enrichment on a host where archive.org is
reachable to get real results.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Optional

from . import config
from .http import fetch


def _cdx_query_url(url_pattern: str, *, match_type: str = "prefix",
                   filters: Optional[list] = None, collapse: Optional[str] = "urlkey",
                   limit: Optional[int] = None) -> str:
    """Build a CDX API request URL with output=json and the given options."""
    params = [
        ("url", url_pattern),
        ("output", "json"),
        ("matchType", match_type),
    ]
    # Each filter is a "field:regex" string, e.g. "statuscode:200".
    for f in (filters or []):
        params.append(("filter", f))
    if collapse:
        params.append(("collapse", collapse))
    if limit:
        params.append(("limit", str(limit)))
    return config.WAYBACK_CDX_URL + "?" + urllib.parse.urlencode(params)


def cdx_search(url_pattern: str, *, match_type: str = "prefix",
               filters: Optional[list] = None, collapse: Optional[str] = "urlkey",
               limit: Optional[int] = None) -> list:
    """Query the CDX API and return a list of dict rows.

    The CDX JSON payload is a list-of-lists where row 0 is the column header
    (typically ["urlkey","timestamp","original","mimetype","statuscode",
    "digest","length"]); we zip that header with every subsequent data row.
    Returns [] on any failure (network blocked, bad JSON, empty result).
    """
    url = _cdx_query_url(url_pattern, match_type=match_type, filters=filters,
                         collapse=collapse, limit=limit)
    raw = fetch(url)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    # Need a header row plus at least one data row.
    if not isinstance(data, list) or len(data) < 2:
        return []
    header = data[0]
    rows = []
    for row in data[1:]:
        # Be tolerant of ragged rows.
        rows.append(dict(zip(header, row)))
    return rows


def snapshot_url(timestamp: str, original: str) -> str:
    """Build a normal (rewritten) Wayback snapshot URL."""
    return f"{config.WAYBACK_BASE}/{timestamp}/{original}"


def snapshot_url_raw(timestamp: str, original: str) -> str:
    """Build the raw ("id_") Wayback variant that serves the original bytes
    without Wayback's HTML rewriting / toolbar injection."""
    return f"{config.WAYBACK_BASE}/{timestamp}id_/{original}"


def earliest_snapshot(url_pattern: str) -> Optional[dict]:
    """Return the status-200 CDX row with the smallest timestamp, or None."""
    rows = cdx_search(url_pattern, filters=["statuscode:200"])
    if not rows:
        return None
    # Timestamps are zero-padded "YYYYMMDDhhmmss" so string order == time order.
    try:
        return min(rows, key=lambda r: r.get("timestamp", "99999999999999"))
    except (ValueError, TypeError):
        return None


def find_brochure_pdfs(query_terms, *, host: str = "places.je",
                       limit: int = 50) -> list:
    """Find archived PDFs (likely agent brochures) under `host`.

    Filters the CDX results to mimetype application/pdf and, when query terms
    are supplied, keeps only originals whose URL contains at least one term.
    Returns de-duplicated snapshot URLs (preferring the earliest capture of
    each distinct original).
    """
    rows = cdx_search(
        host + "/*",
        match_type="domain",
        filters=["mimetype:application/pdf", "statuscode:200"],
        collapse="digest",
        limit=limit,
    )
    if not rows:
        return []
    # Normalise query terms to lowercase tokens for substring matching.
    terms = []
    if isinstance(query_terms, str):
        terms = [t for t in _slug_tokens(query_terms)]
    elif query_terms:
        for q in query_terms:
            terms.extend(_slug_tokens(q))
    terms = [t for t in terms if t]

    seen = set()
    out = []
    for r in rows:
        original = r.get("original", "")
        ts = r.get("timestamp", "")
        if not original or not ts:
            continue
        low = original.lower()
        if terms and not any(t in low for t in terms):
            continue
        if original in seen:
            continue
        seen.add(original)
        out.append(snapshot_url(ts, original))
    return out


# --------------------------------------------------------------------------
# Availability API fallback.
#
# Some egress policies allow the archive.org *apex* (which serves the
# Availability API) while blocking the web.archive.org *subdomain* (which
# serves the CDX server and snapshot content). The Availability API can't do
# wildcard discovery or return snapshot HTML, but it WILL tell us the closest /
# earliest snapshot of an *exact* URL plus an openable snapshot link -- enough
# to recover a first-on-market date when CDX is unreachable.
# --------------------------------------------------------------------------

AVAILABILITY_URL = "https://archive.org/wayback/available"


def availability(url: str, timestamp: str = "19950101") -> Optional[dict]:
    """Return the snapshot closest to `timestamp` for an exact URL, or None.

    Pass an early timestamp (the default) to get the *earliest* capture. The
    returned dict has: timestamp, iso, original, snapshot_url, status.
    """
    q = urllib.parse.urlencode({"url": url, "timestamp": timestamp})
    raw = fetch(f"{AVAILABILITY_URL}?{q}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    snap = (data.get("archived_snapshots") or {}).get("closest")
    if not snap or not snap.get("timestamp"):
        return None
    ts = snap["timestamp"]
    return {
        "timestamp": ts,
        "iso": ts_to_iso(ts),
        "original": url,
        # Normalise to https; the API often returns an http:// snapshot URL.
        "snapshot_url": (snap.get("url") or "").replace("http://", "https://", 1),
        "status": snap.get("status", ""),
    }


def earliest_via_availability(url: str) -> Optional[dict]:
    """Earliest archived capture of `url` via the apex Availability API."""
    return availability(url, timestamp="19950101")


def probe_backends() -> dict:
    """Report which archive/live backends are reachable from this environment.

    Returns {name: bool}. Lets callers (and the `probe` CLI command) explain
    why enrichment is or isn't fully functional here.
    """
    checks = {
        "wayback_cdx (web.archive.org)":
            bool(cdx_search("example.com", limit=1)),
        "availability_api (archive.org apex)":
            availability("example.com") is not None,
        "places_live (www.places.je)":
            bool(fetch(config.BASE_URL + config.SOLD_PATH)),
    }
    return checks


def ts_to_iso(timestamp: str) -> str:
    """Convert a Wayback "YYYYMMDDhhmmss" timestamp to "YYYY-MM-DD".

    Returns "" if the timestamp is too short / malformed.
    """
    ts = (timestamp or "").strip()
    if len(ts) < 8 or not ts[:8].isdigit():
        return ""
    return f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"


def _slug_tokens(text: str) -> list:
    """Lowercase alnum tokens from arbitrary text (helper for term matching)."""
    out, cur = [], []
    for ch in (text or "").lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out
