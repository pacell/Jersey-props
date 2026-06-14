#!/usr/bin/env python3
"""Download direct-PDF brochures referenced in manual_search.json into
site/brochures/ so the app can link to local copies. Non-PDF links (Issuu,
agent listing pages) are skipped. Writes site/brochures/index.json mapping the
SoldProperty key -> list of locally saved files."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jersey_props import config  # noqa: E402

MANUAL = os.path.join(config.DATA_DIR, "manual_search.json")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "site", "brochures")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def is_pdf(url: str) -> bool:
    u = url.lower()
    return u.endswith(".pdf") or "/document-0.pdf" in u or ".pdf?" in u


def slug(key: str, i: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", key.split("|")[0].lower()).strip("-")[:40]
    return f"{base}-{i}.pdf"


def main() -> None:
    manual = json.load(open(MANUAL, encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    index, ok, fail = {}, 0, 0
    for key, v in manual.items():
        saved = []
        for i, url in enumerate(v.get("brochure_pdfs", [])):
            if not is_pdf(url):
                continue
            name = slug(key, i)
            dest = os.path.join(OUT, name)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=40) as r:
                    data = r.read()
                if data[:4] == b"%PDF" and len(data) > 5000:
                    with open(dest, "wb") as f:
                        f.write(data)
                    saved.append(f"brochures/{name}")
                    ok += 1
                    print(f"  ok  {name}  ({len(data)//1024} KB)  <- {url[:60]}")
                else:
                    fail += 1
                    print(f"  skip (not a PDF body) {url[:70]}")
            except Exception as e:  # noqa: BLE001
                fail += 1
                print(f"  FAIL {url[:60]}: {str(e)[:40]}")
        if saved:
            index[key] = saved
    json.dump(index, open(os.path.join(OUT, "index.json"), "w"), indent=2)
    print(f"\ndownloaded {ok} PDFs ({fail} skipped/failed) for "
          f"{len(index)} properties -> {OUT}")


if __name__ == "__main__":
    main()
