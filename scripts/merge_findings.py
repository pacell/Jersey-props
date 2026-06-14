#!/usr/bin/env python3
"""Merge sub-agent brochure-research JSON (/tmp/findings/*.json) into
data/manual_search.json. Matches finding keys to real SoldProperty keys by a
punctuation-insensitive normalisation, and only overwrites a field when the
finding has a non-empty value (so hand-curated entries are never blanked)."""

from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jersey_props import config, storage  # noqa: E402

FINDINGS_GLOB = os.environ.get("FINDINGS_GLOB", "/tmp/findings/*.json")
MANUAL = os.path.join(config.DATA_DIR, "manual_search.json")
FIELDS = ("asking_price", "asking_price_display", "source", "brochure_pdfs",
          "size_sqft", "bedrooms", "bathrooms", "sea_view", "what3words",
          "first_listed_iso", "notes")


def norm(k: str) -> str:
    k = k.lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    k = k.replace("'", "").replace("&amp;", "&")
    return re.sub(r"\s+", " ", k).strip()


def main() -> None:
    sold = storage.load_sold()
    by_norm = {norm(s.key()): s.key() for s in sold}

    manual = {}
    if os.path.exists(MANUAL):
        manual = json.load(open(MANUAL, encoding="utf-8"))

    matched = unmatched = updated = 0
    for path in sorted(glob.glob(FINDINGS_GLOB)):
        findings = json.load(open(path, encoding="utf-8"))
        for fkey, data in findings.items():
            real = by_norm.get(norm(fkey))
            if not real:
                unmatched += 1
                print(f"  ! no sold match for: {fkey[:60]}")
                continue
            matched += 1
            entry = manual.get(real, {})
            changed = False
            for f in FIELDS:
                v = data.get(f)
                if v not in (None, "", [], "not found in public sources"):
                    if entry.get(f) != v:
                        entry[f] = v
                        changed = True
            if changed:
                updated += 1
            manual[real] = entry

    json.dump(manual, open(MANUAL, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    asks = sum(1 for v in manual.values() if v.get("asking_price"))
    bros = sum(1 for v in manual.values() if v.get("brochure_pdfs"))
    print(f"\nmatched {matched}, unmatched {unmatched}, updated {updated}")
    print(f"manual_search.json now: {len(manual)} entries, "
          f"{asks} with asking price, {bros} with brochures")


if __name__ == "__main__":
    main()
