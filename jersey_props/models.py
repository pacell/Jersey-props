"""Data models shared across the pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SoldProperty:
    """A single sold transaction as listed on places.je/sold-property."""

    name: str                      # Property name / primary line
    address: str                   # Secondary address line (road, parish)
    parish: str                    # Best-effort parish extracted from address
    sale_date: str                 # As shown, e.g. "8 May 2026"
    sale_date_iso: str             # Normalised YYYY-MM-DD ("" if unparsed)
    sale_price: int                # In GBP, e.g. 8500000
    sale_price_display: str        # As shown, e.g. "£8,500,000"
    agent: str                     # Selling agent name ("" if not shown)
    agent_slug: str                # places.je agent slug ("" if not shown)
    source_page: int               # Page number it was scraped from

    def key(self) -> str:
        """A stable-ish identity key for de-duplication / joins."""
        return f"{self.name}|{self.sale_date_iso}|{self.sale_price}".lower()


@dataclass
class EnrichedProperty:
    """A sold property cross-indexed with listing history (Wayback etc.)."""

    sold: SoldProperty

    # Asking price discovered from an archived listing (GBP), if any.
    asking_price: Optional[int] = None
    asking_price_display: str = ""
    asking_price_source: str = ""        # URL of the snapshot it came from

    # When the property first appeared on the market (earliest archived
    # snapshot of a matching listing), ISO date.
    first_listed_iso: str = ""
    first_listed_source: str = ""        # Wayback snapshot URL

    # How long it sat before selling (days), if both dates are known.
    days_on_market: Optional[int] = None

    # Asking-vs-sold delta (sale_price - asking_price) and percentage.
    price_delta: Optional[int] = None
    price_delta_pct: Optional[float] = None

    # Agent brochure PDFs found in the Wayback Machine.
    brochure_pdfs: list = field(default_factory=list)

    # Free-form notes about match confidence / problems.
    notes: str = ""

    def to_row(self) -> dict:
        row = asdict(self.sold)
        row.update(
            {
                "asking_price": self.asking_price or "",
                "asking_price_display": self.asking_price_display,
                "asking_price_source": self.asking_price_source,
                "first_listed_iso": self.first_listed_iso,
                "first_listed_source": self.first_listed_source,
                "days_on_market": self.days_on_market if self.days_on_market is not None else "",
                "price_delta": self.price_delta if self.price_delta is not None else "",
                "price_delta_pct": (
                    f"{self.price_delta_pct:.1f}" if self.price_delta_pct is not None else ""
                ),
                "brochure_pdfs": " ".join(self.brochure_pdfs),
                "notes": self.notes,
            }
        )
        return row
