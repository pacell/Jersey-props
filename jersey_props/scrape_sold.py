"""Stage 1: pull sold transactions from the places.je JSON API.

The /sold-property page is server-rendered, but the same endpoint returns clean
JSON when called with `?json=true` -- far more reliable than scraping HTML. Each
result carries name, address, parish, price, an ISO transactionDate and the
selling estate agent. We page through all results at/above `min_price`.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from typing import List

from . import config
from .http import fetch
from .models import SoldProperty


def _api_url(min_price: int, page: int) -> str:
    q = urllib.parse.urlencode({"minPrice": min_price, "page": page, "json": "true"})
    return f"{config.BASE_URL}{config.SOLD_PATH}?{q}"


def _to_record(r: dict, page: int) -> SoldProperty:
    iso = (r.get("transactionDate") or "")[:10]  # "2026-05-29T00:00:00" -> date
    price = int(r.get("price") or 0)
    agent_obj = r.get("estateAgent") or {}
    return SoldProperty(
        name=(r.get("name") or "").strip(),
        address=(r.get("address") or "").strip(),
        parish=(r.get("parish") or "").strip(),
        sale_date=(r.get("displayTransactionDate") or "").strip(),
        sale_date_iso=iso,
        sale_price=price,
        sale_price_display=r.get("displayPrice") or f"£{price:,}",
        agent=(agent_obj.get("name") or "").strip(),
        agent_slug=(agent_obj.get("urlSlug") or "").strip(),
        source_page=page,
    )


def total_transactions(min_price: int = config.DEFAULT_MIN_PRICE) -> int:
    data = _get_json(_api_url(min_price, 1))
    if not data:
        return 0
    return int((data.get("paging") or {}).get("resultCount") or 0)


def _get_json(url: str) -> dict | None:
    raw = fetch(url)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def scrape(min_price: int = config.DEFAULT_MIN_PRICE,
           max_pages: int | None = None,
           verbose: bool = True) -> List[SoldProperty]:
    """Page through the sold-property JSON API and return all transactions."""
    first = _get_json(_api_url(min_price, 1))
    if not first:
        if verbose:
            print("Failed to fetch page 1")
        return []
    paging = first.get("paging") or {}
    total = int(paging.get("resultCount") or 0)
    pages = int(paging.get("totalPages") or 0)
    if max_pages:
        pages = min(pages, max_pages) if pages else max_pages
    if verbose:
        print(f"Sold transactions >= £{min_price:,}: {total} across {pages} pages")

    results: List[SoldProperty] = []
    seen: set[str] = set()

    def ingest(data: dict, page: int) -> int:
        new = 0
        for r in data.get("results", []):
            rec = _to_record(r, page)
            if rec.key() in seen:
                continue
            seen.add(rec.key())
            results.append(rec)
            new += 1
        return new

    new = ingest(first, 1)
    if verbose:
        print(f"  page 1: {new} new | total {len(results)}")
    for page in range(2, pages + 1):
        data = _get_json(_api_url(min_price, page))
        if not data:
            if verbose:
                print(f"  page {page}: fetch failed, stopping")
            break
        new = ingest(data, page)
        if verbose:
            print(f"  page {page}: {new} new | total {len(results)}")
        time.sleep(config.REQUEST_DELAY_SECONDS)
    return results
