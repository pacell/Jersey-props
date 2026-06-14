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


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def main() -> None:
    enr = storage.load_enriched_rows()
    manual = _load_json(os.path.join(config.DATA_DIR, "manual_search.json"), {})
    local_broch = _load_json(os.path.join(SITE_DIR, "brochures", "index.json"), {})
    out = []
    for i, r in enumerate(enr, 1):
        if i % 100 == 0:
            geocode.save_cache()
            print(f"  ...{i}/{len(enr)} geocoded")
        name, address, parish = r["name"], r.get("address", ""), r.get("parish", "")
        price = int(r["sale_price"]) if r.get("sale_price") else 0
        key = f"{name}|{r.get('sale_date_iso','')}|{price}".lower()
        m = manual.get(key, {})

        # Metrics: prefer agent findings, fall back to mining the notes text.
        metrics = dict(metrics_from_text(r.get("notes", "")))
        for f in ("size_sqft", "bedrooms", "bathrooms", "acres", "what3words"):
            if m.get(f) not in (None, "", []):
                metrics[f] = m[f]
        # Sea view: agent flag, else locality keyword heuristic.
        sea = m.get("sea_view")
        if sea is None:
            blob = f"{name} {address} {parish}".lower()
            sea = any(k in blob for k in SEA_KW)

        # Brochures: locally-saved PDFs first, then remaining remote links.
        remote = [u for u in (r.get("brochure_pdfs") or "").split() if u]
        brochures = list(dict.fromkeys(local_broch.get(key, []) + remote))

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
            "sea_view": bool(sea),
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
    n_ask = sum(1 for p in out if p["asking_price"])
    n_bro = sum(1 for p in out if p["brochures"])
    print(f"wrote {len(out)} properties -> {path} "
          f"({n_ask} asking, {n_bro} brochures)")


if __name__ == "__main__":
    main()
