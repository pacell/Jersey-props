"""Stage 1: scrape sold transactions from places.je/sold-property.

The results page is server-rendered HTML. Each transaction is a card:

    <div class="bg-white p-3 mb-2"><div class="form-row">
      <div ...><div style="min-width:100px">8 May 2026</div></div>
      <div ...><div><strong>NAME, PARISH</strong><span>, ROAD, PARISH</span></div>
        <div ...><a href="/estate-agents/SLUG"><strong>Sold</strong> by AGENT</a></div>
      </div>
      <div ...><strong style="color:#65cccc">£8,500,000</strong></div>
    </div></div>

We parse with the standard library only (re + html) so the scraper runs in a
locked-down sandbox with no third-party packages.
"""

from __future__ import annotations

import html
import re
import time
import urllib.parse
from typing import Iterator, List

from . import config
from .http import fetch
from .models import SoldProperty

# Split the results region into per-transaction cards.
_CARD_RE = re.compile(r'<div class="bg-white p-3 mb-2">(.*?)</div></div></div>', re.S)
_DATE_RE = re.compile(r'min-width:100px">([^<]+)</div>')
_PRICE_RE = re.compile(r'color:#65cccc">\s*£([\d,]+)')
_NAME_RE = re.compile(r'<div><strong>(.*?)</strong>(?:<span>(.*?)</span>)?', re.S)
_AGENT_RE = re.compile(r'href="/estate-agents/([^"]+)"[^>]*>.*?by\s*(?:<!--\s*-->)?\s*([^<]+)</a>', re.S)
_COUNT_RE = re.compile(r'([\d,]+)<!-- --> transactions')

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"]
    )
}
# Allow 3-letter abbreviations too.
for _full, _i in list(_MONTHS.items()):
    _MONTHS[_full[:3]] = _i


def _clean(text: str) -> str:
    """Strip tags/comments and unescape HTML entities."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip().strip(",").strip()


def _parse_date(raw: str) -> str:
    """'8 May 2026' -> '2026-05-08' (best effort, '' on failure)."""
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw.strip())
    if not m:
        return ""
    day, mon, year = m.group(1), m.group(2).lower(), m.group(3)
    month = _MONTHS.get(mon)
    if not month:
        return ""
    return f"{int(year):04d}-{month:02d}-{int(day):02d}"


def _parish_from(address: str, name: str) -> str:
    """Best-effort parish: last comma-separated chunk that looks like St.X."""
    for chunk in reversed([c.strip() for c in (address or name).split(",")]):
        if re.search(r"\b(St\.?|Saint|Grouville|Trinity|Town)\b", chunk, re.I):
            return chunk
    parts = [c.strip() for c in (address or name).split(",") if c.strip()]
    return parts[-1] if parts else ""


def total_transactions(min_price: int = config.DEFAULT_MIN_PRICE) -> int:
    """Return the total transaction count the site reports for this filter."""
    url = _page_url(min_price, 1)
    page = fetch(url)
    if not page:
        return 0
    m = _COUNT_RE.search(page)
    return int(m.group(1).replace(",", "")) if m else 0


def _page_url(min_price: int, page: int) -> str:
    q = urllib.parse.urlencode({"minPrice": min_price, "page": page})
    return f"{config.BASE_URL}{config.SOLD_PATH}?{q}"


def parse_cards(page_html: str, page_num: int) -> List[SoldProperty]:
    out: List[SoldProperty] = []
    for block in _CARD_RE.findall(page_html):
        price_m = _PRICE_RE.search(block)
        date_m = _DATE_RE.search(block)
        name_m = _NAME_RE.search(block)
        if not (price_m and name_m):
            continue
        name = _clean(name_m.group(1))
        address = _clean(name_m.group(2) or "")
        raw_date = date_m.group(1).strip() if date_m else ""
        agent_m = _AGENT_RE.search(block)
        price = int(price_m.group(1).replace(",", ""))
        out.append(
            SoldProperty(
                name=name,
                address=address,
                parish=_parish_from(address, name),
                sale_date=raw_date,
                sale_date_iso=_parse_date(raw_date),
                sale_price=price,
                sale_price_display=f"£{price:,}",
                agent=_clean(agent_m.group(2)) if agent_m else "",
                agent_slug=agent_m.group(1) if agent_m else "",
                source_page=page_num,
            )
        )
    return out


def scrape(min_price: int = config.DEFAULT_MIN_PRICE,
           max_pages: int | None = None,
           verbose: bool = True) -> List[SoldProperty]:
    """Scrape all sold transactions at or above `min_price`."""
    total = total_transactions(min_price)
    pages = -(-total // config.RESULTS_PER_PAGE) if total else 0  # ceil div
    if max_pages:
        pages = min(pages, max_pages) if pages else max_pages
    if verbose:
        print(f"Sold transactions >= £{min_price:,}: {total} across ~{pages} pages")

    results: List[SoldProperty] = []
    seen: set[str] = set()
    page = 1
    while True:
        if pages and page > pages:
            break
        url = _page_url(min_price, page)
        page_html = fetch(url)
        if not page_html:
            if verbose:
                print(f"  page {page}: fetch failed, stopping")
            break
        cards = parse_cards(page_html, page)
        if not cards:
            if verbose:
                print(f"  page {page}: no cards, stopping")
            break
        new = 0
        for c in cards:
            if c.key() in seen:
                continue
            seen.add(c.key())
            results.append(c)
            new += 1
        if verbose:
            print(f"  page {page}: {len(cards)} cards ({new} new) | running total {len(results)}")
        if not pages and len(cards) < config.RESULTS_PER_PAGE:
            break
        page += 1
        time.sleep(config.REQUEST_DELAY_SECONDS)
    return results


def iter_scrape(*args, **kwargs) -> Iterator[SoldProperty]:
    yield from scrape(*args, **kwargs)
