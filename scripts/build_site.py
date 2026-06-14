#!/usr/bin/env python3
"""Build site/data.json for the mobile web app from the enriched dataset.

For each sold record: carry sale/asking/discount/agent/brochures, geocode it for
the map, and attach key metrics (size, beds, sea view) -- scraped from the
brochure where one exists, otherwise inferred from text/locality.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jersey_props import config, storage, geocode          # noqa: E402
from jersey_props.brochure import fetch_metrics, metrics_from_text  # noqa: E402

SITE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
SEA_KW = ("bay", "aubin", "ouaisne", "ouaisné", "gorey", "rozel", "brelade",
          "corbiere", "corbière", "beach", "cliff", "coast", "sea", "mielles",
          "havre", "plage", "lecq", "bonne nuit", "bouley")


def main() -> None:
    enr = storage.load_enriched_rows()
    out = []
    scraped = 0
    geo_hits = 0
    for i, r in enumerate(enr, 1):
        if i % 100 == 0:
            geocode.save_cache()
            print(f"  ...{i}/{len(enr)} geocoded")
        name, address, parish = r["name"], r.get("address", ""), r.get("parish", "")
        brochures = [u for u in (r.get("brochure_pdfs") or "").split() if u]
        metrics = {}
        if brochures:
            metrics = fetch_metrics(brochures, r.get("notes", ""))
            scraped += 1
            time.sleep(config.REQUEST_DELAY_SECONDS)
        else:
            metrics = metrics_from_text(r.get("notes", ""))
        # Island-wide sea-view hint from locality keywords (if not already set).
        if "sea_view" not in metrics:
            blob = f"{name} {address} {parish}".lower()
            if any(k in blob for k in SEA_KW):
                metrics["sea_view"] = True
        lat, lng = geocode.geocode(parish, name, address)
        out.append({
            "name": name,
            "address": address,
            "parish": parish,
            "sale_date": r.get("sale_date_iso", ""),
            "sale_price": int(r["sale_price"]) if r.get("sale_price") else None,
            "sale_display": r.get("sale_price_display", ""),
            "asking_price": int(r["asking_price"]) if r.get("asking_price") else None,
            "asking_display": r.get("asking_price_display", ""),
            "discount_pct": (float(r["price_delta_pct"]) if r.get("price_delta_pct") else None),
            "agent": r.get("agent", ""),
            "brochures": brochures,
            "first_listed": r.get("first_listed_iso", ""),
            "size_sqft": metrics.get("size_sqft"),
            "bedrooms": metrics.get("bedrooms"),
            "bathrooms": metrics.get("bathrooms"),
            "acres": metrics.get("acres"),
            "sea_view": bool(metrics.get("sea_view", False)),
            "what3words": metrics.get("what3words", ""),
            "notes": r.get("notes", ""),
            "lat": lat, "lng": lng,
        })

    geocode.save_cache()
    os.makedirs(SITE_DIR, exist_ok=True)
    path = os.path.join(SITE_DIR, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%d"),
                   "count": len(out), "properties": out}, f, ensure_ascii=False)
    print(f"wrote {len(out)} properties -> {path} (brochure-scraped {scraped})")


if __name__ == "__main__":
    main()
