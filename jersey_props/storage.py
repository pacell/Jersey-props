"""CSV / JSON persistence for scraped and enriched records."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from typing import List

from . import config
from .models import SoldProperty, EnrichedProperty


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def save_sold(records: List[SoldProperty], stem: str = "sold_2m_plus") -> tuple[str, str]:
    json_path = os.path.join(config.DATA_DIR, f"{stem}.json")
    csv_path = os.path.join(config.DATA_DIR, f"{stem}.csv")
    _ensure_dir(json_path)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, indent=2, ensure_ascii=False)

    if records:
        fields = list(asdict(records[0]).keys())
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in records:
                w.writerow(asdict(r))
    return json_path, csv_path


def load_sold(stem: str = "sold_2m_plus") -> List[SoldProperty]:
    json_path = os.path.join(config.DATA_DIR, f"{stem}.json")
    with open(json_path, encoding="utf-8") as f:
        return [SoldProperty(**row) for row in json.load(f)]


def load_enriched_rows(stem: str = "sold_2m_plus_enriched") -> List[dict]:
    """Load the enriched dataset back as plain dict rows (as written to JSON)."""
    json_path = os.path.join(config.DATA_DIR, f"{stem}.json")
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def save_enriched(records: List[EnrichedProperty], stem: str = "sold_2m_plus_enriched") -> tuple[str, str]:
    json_path = os.path.join(config.DATA_DIR, f"{stem}.json")
    csv_path = os.path.join(config.DATA_DIR, f"{stem}.csv")
    _ensure_dir(json_path)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([r.to_row() for r in records], f, indent=2, ensure_ascii=False)

    if records:
        fields = list(records[0].to_row().keys())
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in records:
                w.writerow(r.to_row())
    return json_path, csv_path
