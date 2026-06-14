"""Stage 2/3: enrich each SoldProperty with archived listing history.

For every sold transaction we ask the Wayback Machine for archived snapshots
of the original places.je listing and try to recover:
  * the original asking / guide price,
  * the date it first went on the market, and
  * any agent brochure PDFs.

Nothing here ever raises: network and parse problems are caught and recorded
in the EnrichedProperty.notes field so the pipeline always produces a row.

IMPORTANT: requires web.archive.org to be reachable (see wayback.py).
"""

from __future__ import annotations

import html as html_mod
import re
import time
from datetime import date
from typing import Optional, Tuple

from . import config
from .http import fetch
from .models import EnrichedProperty, SoldProperty
from . import wayback


# A £ amount, optionally with comma thousands separators and ".00" pence.
_PRICE_RE = re.compile(r"£\s*([0-9][0-9,]{2,})(?:\.\d{2})?")
# Words that signal the figure right next to them is an asking price.
_CUE_WORDS = ("guide", "asking", "price", "offers", "oieo", "oiro")
_POA_RE = re.compile(r"price on application|\bP\.?O\.?A\.?\b", re.IGNORECASE)


def _slugify(text: str) -> str:
    """lowercase, punctuation stripped, spaces -> single hyphens."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _tokens(text: str) -> set:
    """Set of lowercase alnum tokens (length >= 2) for overlap scoring."""
    return {t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) >= 2}


def extract_asking_price(snapshot_html: str) -> Tuple[Optional[int], str]:
    """Pull an asking price out of archived listing HTML.

    Strategy: strip tags, look for £ amounts that sit near a price cue word
    ("Guide", "Asking", "Price"...). Prefer cue-adjacent figures; fall back to
    the largest plausible £ figure on the page. Recognise "Price on
    Application" / POA. Returns (price_int_or_None, display_string).
    """
    if not snapshot_html:
        return None, ""
    try:
        # Unescape entities (&pound; etc.) and flatten tags to plain text.
        text = html_mod.unescape(snapshot_html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
    except Exception:  # noqa: BLE001 - never let parsing kill enrichment
        return None, ""

    # Collect every £ amount with its character offset for proximity scoring.
    candidates = []  # (value:int, display:str, pos:int)
    for m in _PRICE_RE.finditer(text):
        digits = m.group(1).replace(",", "")
        if not digits.isdigit():
            continue
        value = int(digits)
        # Ignore obviously-too-small figures (fees, monthly rents, etc.).
        if value < 10_000:
            continue
        candidates.append((value, m.group(0).strip(), m.start()))

    if not candidates:
        # No figure: maybe it's POA.
        if _POA_RE.search(text):
            return None, "Price on Application"
        return None, ""

    # Score by nearness to a cue word within a small window before the figure.
    def cue_score(pos: int) -> int:
        window = text[max(0, pos - 40):pos].lower()
        return sum(1 for w in _CUE_WORDS if w in window)

    cued = [c for c in candidates if cue_score(c[2]) > 0]
    pool = cued if cued else candidates
    # Among the chosen pool take the largest figure (asking prices dominate
    # incidental small amounts on a listing page).
    best = max(pool, key=lambda c: c[0])
    return best[0], best[1]


def _candidate_patterns(sold: SoldProperty) -> list:
    """Build plausible places.je listing URL patterns for a property."""
    name_slug = _slugify(sold.name)
    addr_slug = _slugify(sold.address)
    combo = _slugify(f"{sold.name} {sold.address}")
    patterns = []
    for slug in (name_slug, combo, addr_slug):
        if not slug:
            continue
        patterns.append(f"places.je/property/{slug}*")
        patterns.append(f"places.je/*{slug}*for-sale*")
        patterns.append(f"places.je/*{slug}*")
    # De-duplicate while preserving order.
    seen, out = set(), []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _matching_snapshots(sold: SoldProperty) -> list:
    """Return CDX rows whose original URL plausibly matches this property.

    A row matches when its URL tokens overlap meaningfully with the property's
    name/address tokens. Searches each candidate pattern until matches appear.
    """
    want = _tokens(f"{sold.name} {sold.address}")
    if not want:
        return []
    matches = []
    for pattern in _candidate_patterns(sold):
        rows = wayback.cdx_search(
            pattern, match_type="prefix",
            filters=["statuscode:200", "mimetype:text/html"],
            collapse="digest", limit=200,
        )
        for r in rows:
            url_tokens = _tokens(r.get("original", ""))
            overlap = want & url_tokens
            # Require at least two shared tokens to avoid spurious matches.
            if len(overlap) >= 2:
                r = dict(r)
                r["_overlap"] = len(overlap)
                matches.append(r)
        if matches:
            break  # first pattern that yields hits is good enough
    return matches


def enrich_property(sold: SoldProperty) -> EnrichedProperty:
    """Cross-index one SoldProperty against the Wayback Machine.

    Never raises: every network/parse step is guarded and any problem is
    appended to `notes`.
    """
    ep = EnrichedProperty(sold=sold)
    notes = []

    # ---- Find archived listing snapshots that match this property. --------
    matches = []
    try:
        matches = _matching_snapshots(sold)
    except Exception as e:  # noqa: BLE001
        notes.append(f"snapshot search failed: {e}")

    if matches:
        best_overlap = max(m.get("_overlap", 0) for m in matches)
        notes.append(f"{len(matches)} matching snapshot(s), "
                     f"max token overlap {best_overlap}")
        # Earliest matching capture = first time it appeared on the market.
        earliest = min(matches, key=lambda r: r.get("timestamp", "9" * 14))
        ts = earliest.get("timestamp", "")
        original = earliest.get("original", "")
        ep.first_listed_iso = wayback.ts_to_iso(ts)
        ep.first_listed_source = wayback.snapshot_url(ts, original)

        # ---- Fetch that snapshot and read the asking price. --------------
        try:
            snap_html = fetch(wayback.snapshot_url(ts, original))
            if snap_html:
                price, display = extract_asking_price(snap_html)
                if price is not None:
                    ep.asking_price = price
                    ep.asking_price_display = display
                    ep.asking_price_source = ep.first_listed_source
                elif display:
                    ep.asking_price_display = display  # e.g. "Price on Application"
                    ep.asking_price_source = ep.first_listed_source
                else:
                    notes.append("no price found in earliest snapshot")
            else:
                notes.append("could not fetch earliest snapshot")
        except Exception as e:  # noqa: BLE001
            notes.append(f"price extraction failed: {e}")
    else:
        notes.append("no matching listing snapshot found")

    # ---- Derived metrics: days on market, asking-vs-sold delta. ----------
    try:
        if ep.first_listed_iso and sold.sale_date_iso:
            d_first = date.fromisoformat(ep.first_listed_iso)
            d_sold = date.fromisoformat(sold.sale_date_iso)
            ep.days_on_market = (d_sold - d_first).days
    except (ValueError, TypeError) as e:
        notes.append(f"days_on_market calc failed: {e}")

    try:
        if ep.asking_price and sold.sale_price:
            ep.price_delta = sold.sale_price - ep.asking_price
            ep.price_delta_pct = (ep.price_delta / ep.asking_price) * 100.0
    except (TypeError, ZeroDivisionError) as e:
        notes.append(f"price_delta calc failed: {e}")

    # ---- Agent brochure PDFs. --------------------------------------------
    try:
        ep.brochure_pdfs = wayback.find_brochure_pdfs(
            f"{sold.name} {sold.address}", host="places.je", limit=50
        )
    except Exception as e:  # noqa: BLE001
        notes.append(f"brochure search failed: {e}")

    ep.notes = "; ".join(notes)
    return ep


def enrich_all(sold_list, *, delay: Optional[float] = None,
               progress: bool = True) -> list:
    """Enrich a list of SoldProperty records with a polite inter-request delay."""
    if delay is None:
        delay = config.REQUEST_DELAY_SECONDS
    out = []
    total = len(sold_list)
    for i, sold in enumerate(sold_list, 1):
        if progress:
            print(f"[{i}/{total}] enriching: {sold.name} ({sold.sale_date_iso})")
        out.append(enrich_property(sold))
        # Don't sleep after the final item.
        if i < total and delay:
            time.sleep(delay)
    return out
