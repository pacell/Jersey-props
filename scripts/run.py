#!/usr/bin/env python3
"""Command-line entry point for the Jersey property pipeline.

Examples:
    # Stage 1 only: scrape every sold transaction >= £2m
    python3 scripts/run.py scrape

    # Scrape with a custom floor / page cap
    python3 scripts/run.py scrape --min-price 5000000 --max-pages 3

    # Stage 2/3: cross-index the scraped data against the Wayback Machine
    # (run this where web.archive.org is reachable)
    python3 scripts/run.py enrich
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jersey_props import config, storage          # noqa: E402
from jersey_props.scrape_sold import scrape         # noqa: E402


def cmd_scrape(args: argparse.Namespace) -> None:
    records = scrape(min_price=args.min_price, max_pages=args.max_pages)
    records.sort(key=lambda r: (r.sale_date_iso or "0000"), reverse=True)
    json_path, csv_path = storage.save_sold(records, stem=args.stem)
    print(f"\nSaved {len(records)} records:")
    print(f"  {json_path}")
    print(f"  {csv_path}")
    _summary(records)


def _summary(records) -> None:
    if not records:
        return
    total = sum(r.sale_price for r in records)
    top = max(records, key=lambda r: r.sale_price)
    print("\n--- summary ---")
    print(f"  transactions : {len(records)}")
    print(f"  total value  : £{total:,}")
    print(f"  highest      : {top.sale_price_display}  {top.name[:50]}")
    # agent league table
    counts: dict[str, int] = {}
    for r in records:
        if r.agent:
            counts[r.agent] = counts.get(r.agent, 0) + 1
    if counts:
        print("  top agents   :")
        for agent, n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]:
            print(f"      {n:>3}  {agent}")


def cmd_enrich(args: argparse.Namespace) -> None:
    from jersey_props.enrich import enrich_all
    sold = storage.load_sold(stem=args.stem)
    if args.limit:
        sold = sold[: args.limit]
    enriched = enrich_all(sold)
    json_path, csv_path = storage.save_enriched(enriched, stem=f"{args.stem}_enriched")
    print(f"\nSaved {len(enriched)} enriched records:")
    print(f"  {json_path}")
    print(f"  {csv_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Jersey sold-property scraper & cross-indexer")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scrape", help="Stage 1: scrape sold transactions")
    s.add_argument("--min-price", type=int, default=config.DEFAULT_MIN_PRICE)
    s.add_argument("--max-pages", type=int, default=None)
    s.add_argument("--stem", default="sold_2m_plus")
    s.set_defaults(func=cmd_scrape)

    e = sub.add_parser("enrich", help="Stage 2/3: cross-index against Wayback Machine")
    e.add_argument("--stem", default="sold_2m_plus")
    e.add_argument("--limit", type=int, default=None)
    e.set_defaults(func=cmd_enrich)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
