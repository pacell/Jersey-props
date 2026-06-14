"""Stages 2-3: cross-index each sold transaction with listing data.

places.je blocks bots, so web archives (Wayback / Common Crawl) barely captured
it -- historical listing snapshots are mostly unavailable. So we enrich from the
sources that *do* work, in priority order:

  1. Live places.je listings (JSON API) -- exact asking price + `publishedAt`
     first-listed date for any sold property still / again on the market.
  2. Web-search findings (data/manual_search.json) -- agent brochure PDFs and
     guide prices found by searching the web per property (the brochures carry
     the guide price in their title). Populate this file with `search_enrich`
     or by hand; it is keyed by SoldProperty.key() or by property name.
  3. Wayback Availability API -- recovers a first-listed *date* for any exact
     places.je URL it can resolve (archive.org apex; works where the
     web.archive.org subdomain is blocked).

Nothing here raises: every step is guarded and problems are noted in `notes`.
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import time
from datetime import date
from typing import Optional, Tuple

from . import config
from .http import fetch
from .models import EnrichedProperty, SoldProperty
from . import wayback, places_live


_PRICE_RE = re.compile(r"£\s*([0-9][0-9,]{2,})(?:\.\d{2})?")
_CUE_WORDS = ("guide", "asking", "price", "offers", "oieo", "oiro")
_POA_RE = re.compile(r"price on application|\bP\.?O\.?A\.?\b", re.IGNORECASE)


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (text or "").lower())
    return text.strip("-")


def extract_asking_price(snapshot_html: str) -> Tuple[Optional[int], str]:
    """Pull an asking price out of listing/brochure HTML (cue-word proximity)."""
    if not snapshot_html:
        return None, ""
    try:
        text = html_mod.unescape(snapshot_html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
    except Exception:  # noqa: BLE001
        return None, ""
    candidates = []
    for m in _PRICE_RE.finditer(text):
        digits = m.group(1).replace(",", "")
        if digits.isdigit() and int(digits) >= 100_000:
            candidates.append((int(digits), m.group(0).strip(), m.start()))
    if not candidates:
        return (None, "Price on Application") if _POA_RE.search(text) else (None, "")

    def cue(pos: int) -> int:
        window = text[max(0, pos - 40):pos].lower()
        return sum(1 for w in _CUE_WORDS if w in window)

    cued = [c for c in candidates if cue(c[2]) > 0]
    best = max(cued or candidates, key=lambda c: c[0])
    return best[0], best[1]


def _exact_candidate_urls(sold: SoldProperty) -> list:
    """Best-effort exact places.je URLs to try against the Availability API."""
    urls, seen = [], set()
    for slug in (_slugify(sold.name), _slugify(f"{sold.name} {sold.address}")):
        u = f"www.places.je/property/{slug}"
        if slug and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def _load_manual() -> dict:
    path = os.path.join(config.DATA_DIR, "manual_search.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return {}
    return {}


def _derive(ep: EnrichedProperty, sold: SoldProperty, notes: list) -> None:
    """Compute days-on-market and asking-vs-sold deltas where possible."""
    try:
        if ep.first_listed_iso and sold.sale_date_iso:
            ep.days_on_market = (date.fromisoformat(sold.sale_date_iso)
                                 - date.fromisoformat(ep.first_listed_iso)).days
    except (ValueError, TypeError) as e:
        notes.append(f"days_on_market calc failed: {e}")
    try:
        if ep.asking_price and sold.sale_price:
            ep.price_delta = sold.sale_price - ep.asking_price
            ep.price_delta_pct = (ep.price_delta / ep.asking_price) * 100.0
    except (TypeError, ZeroDivisionError) as e:
        notes.append(f"price_delta calc failed: {e}")


def enrich_property(sold: SoldProperty, live_index=None, manual=None,
                    use_wayback: bool = False, use_live: bool = False) -> EnrichedProperty:
    """Cross-index one SoldProperty from all available sources. Never raises.

    Sources: verified web-search findings (manual) are authoritative; live
    listing matches (use_live) are opt-in because they describe a *current
    re-listing* (a different, present-day asking price) rather than the asking
    price at the time of sale, and name collisions make them noisy.
    """
    ep = EnrichedProperty(sold=sold)
    manual = manual if manual is not None else {}
    notes = []

    # 1. Live listing match -- opt-in flip detector (current re-listing).
    try:
        L = live_index.match(sold.name, sold.address) if (use_live and live_index) else None
        if L:
            f = places_live.LiveIndex.listing_fields(L)
            if f["asking_price"]:
                ep.asking_price = f["asking_price"]
                ep.asking_price_display = f["asking_price_display"]
                ep.asking_price_source = f["listing_url"]
            elif f["asking_price_display"]:
                ep.asking_price_display = f["asking_price_display"]
                ep.asking_price_source = f["listing_url"]
            if f["published_at"]:
                ep.first_listed_iso = f["published_at"]
                ep.first_listed_source = f["listing_url"]
            notes.append(f"current re-listing: property {f['property_id']} "
                         f"({f['agent'] or 'agent n/a'}) -- present-day asking, "
                         f"not the sale-time asking")
    except Exception as e:  # noqa: BLE001
        notes.append(f"live match failed: {e}")

    # 2. Web-search findings (brochure PDFs + guide price + first-listed).
    m = manual.get(sold.key()) or manual.get(sold.name)
    if m:
        if m.get("asking_price") and not ep.asking_price:
            ep.asking_price = int(m["asking_price"])
            ep.asking_price_display = m.get("asking_price_display",
                                            f"£{int(m['asking_price']):,}")
            ep.asking_price_source = m.get("source", "web search")
        if m.get("first_listed_iso") and not ep.first_listed_iso:
            ep.first_listed_iso = m["first_listed_iso"]
            ep.first_listed_source = m.get("source", "web search")
        if m.get("brochure_pdfs"):
            ep.brochure_pdfs = list(dict.fromkeys(ep.brochure_pdfs + list(m["brochure_pdfs"])))
        notes.append(m.get("notes", "web-search enrichment"))

    # 3. Wayback Availability API: first-listed date if still unknown.
    if use_wayback and not ep.first_listed_iso:
        try:
            for url in _exact_candidate_urls(sold):
                snap = wayback.earliest_via_availability(url)
                if snap and snap.get("iso"):
                    ep.first_listed_iso = snap["iso"]
                    ep.first_listed_source = snap["snapshot_url"]
                    notes.append("first-listed via Availability API (date only)")
                    break
        except Exception as e:  # noqa: BLE001
            notes.append(f"availability fallback failed: {e}")

    _derive(ep, sold, notes)
    if not any(notes):
        notes.append("no listing data found in any source")
    ep.notes = "; ".join(n for n in notes if n)
    return ep


def enrich_all(sold_list, *, live_index=None, manual=None, use_wayback: bool = False,
               use_live: bool = False, delay: Optional[float] = None,
               progress: bool = True) -> list:
    """Enrich every sold record from verified findings (+ optional live/wayback)."""
    if use_live and live_index is None:
        if progress:
            print("Building live-listings index ...")
        live_index = places_live.LiveIndex(
            places_live.fetch_all_listings(min_price=0, verbose=progress))
    if manual is None:
        manual = _load_manual()
    if delay is None:
        delay = config.REQUEST_DELAY_SECONDS

    out, total, hits = [], len(sold_list), 0
    for i, sold in enumerate(sold_list, 1):
        ep = enrich_property(sold, live_index, manual, use_wayback, use_live)
        out.append(ep)
        if ep.asking_price or ep.brochure_pdfs:
            hits += 1
            if progress:
                print(f"  + {sold.name[:44]:44} asking={ep.asking_price_display or '-':>22} "
                      f"brochures={len(ep.brochure_pdfs)}")
        if use_wayback and i < total and delay:
            time.sleep(delay)
    if progress:
        print(f"\nEnriched {hits}/{total} with asking price and/or brochure.")
    return out
