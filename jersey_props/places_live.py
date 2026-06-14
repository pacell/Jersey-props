"""Build an index of *currently* on-market places.je listings via the JSON API.

The for-sale search endpoint returns rich JSON (?json=true): propertyId, price,
isPOA, displayPrice, estateAgent, bedrooms, and -- crucially -- `publishedAt`
(when the listing first went live). If a sold property is still (or again) on
the market we can recover its asking price + first-listed date by matching
address. Exact, no archive needed; recall is limited to whatever is live now.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from typing import List, Optional

from . import config
from .http import fetch

BUY_PATH = "/propertysearch/residential-buy"


# Parish names, road particles and listing boilerplate -- none of these
# distinguish one property from another, so they must not drive a match.
_STOP = {
    # articles / prepositions / connectors
    "the", "and", "with", "to", "be", "of", "at", "on", "or", "a",
    # "formerly known as / previously called" clauses
    "formerly", "known", "previously", "called", "also", "now", "aka", "was",
    "before", "that", "name", "names",
    # road particles
    "rue", "route", "mont", "la", "le", "les", "des", "du", "de", "del", "du",
    "clos", "chemin", "ville", "rond", "point",
    # parishes / geography
    "st", "ste", "saint", "jersey", "channel", "islands", "island",
    "brelade", "helier", "saviour", "clement", "lawrence", "peter", "peters",
    "ouen", "mary", "marys", "martin", "john", "johns", "trinity", "grouville",
}


def _norm_tokens(text: str) -> set:
    """Lowercase alnum tokens >=3 chars, minus parish/road/boilerplate noise."""
    toks = {t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) >= 3}
    return toks - _STOP


def _listing_url(page: int, min_price: int) -> str:
    q = urllib.parse.urlencode({"minPrice": min_price, "page": page, "json": "true"})
    return f"{config.BASE_URL}{BUY_PATH}?{q}"


def fetch_all_listings(min_price: int = 0, max_pages: int | None = None,
                       verbose: bool = True) -> List[dict]:
    """Page through current sale listings and return raw result dicts."""
    out: List[dict] = []
    raw = fetch(_listing_url(1, min_price))
    if not raw:
        return out
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return out
    pages = int((data.get("paging") or {}).get("totalPages") or 1)
    if max_pages:
        pages = min(pages, max_pages)
    out.extend(data.get("results", []))
    if verbose:
        print(f"Live listings >= £{min_price:,}: {(data.get('paging') or {}).get('resultCount')} "
              f"across {pages} pages")
    for page in range(2, pages + 1):
        raw = fetch(_listing_url(page, min_price))
        if not raw:
            break
        try:
            out.extend(json.loads(raw).get("results", []))
        except (ValueError, TypeError):
            break
        time.sleep(config.REQUEST_DELAY_SECONDS)
    return out


class LiveIndex:
    """Address-token index over current listings for fuzzy sold->live matching."""

    def __init__(self, listings: List[dict]):
        self.listings = listings
        self._entries = []
        for L in listings:
            blob = f"{L.get('displayAddress','')} {L.get('address','')}"
            self._entries.append((_norm_tokens(blob), L))

    def match(self, name: str, address: str) -> Optional[dict]:
        """Return the live listing that is the *same* property, or None.

        Matches on the distinctive house-name tokens only (parish/road words are
        stripped). A listing qualifies when it contains *every* distinctive name
        token and that name carries enough signal (a >=4-char token, or two
        tokens) -- so re-listed ("flipped") properties are found without the
        parish-token false positives that plague loose overlap matching.
        """
        name_toks = _norm_tokens(name)
        if not name_toks:
            return None
        strong = any(len(t) >= 4 for t in name_toks) or len(name_toks) >= 2
        if not strong:
            return None
        best, best_extra = None, -1
        for toks, L in self._entries:
            if name_toks <= toks:  # every distinctive name token present
                extra = len(_norm_tokens(f"{name} {address}") & toks)
                if extra > best_extra:
                    best, best_extra = L, extra
        return best

    @staticmethod
    def listing_fields(L: dict) -> dict:
        """Pull the enrichment-relevant fields out of a live listing dict."""
        pid = L.get("propertyId")
        return {
            "property_id": pid,
            "listing_url": f"{config.BASE_URL}/property/{pid}" if pid else "",
            "asking_price": None if L.get("isPOA") else int(L.get("price") or 0) or None,
            "asking_price_display": "Price on Application" if L.get("isPOA")
                                    else L.get("displayPrice", ""),
            "published_at": (L.get("publishedAt") or "")[:10],
            "agent": (L.get("estateAgent") or {}).get("name", ""),
        }
