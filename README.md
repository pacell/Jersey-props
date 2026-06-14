# Jersey Properties — sold-price scraper & cross-indexer

Scrapes **actual sold prices** of high-value Jersey (Channel Islands) homes from
[places.je](https://www.places.je/sold-property/) and cross-indexes each sale
against agent listings/brochures to recover the **asking/guide price**, the
**discount to asking**, **agent brochures**, and (where available) when it first
went on the market.

Standard-library only (Python 3.10+) — **zero `pip install`**.

## Results (this run)

- **985 transactions ≥ £2,000,000**, total **£4.14bn** (mean £4.2m) — `data/sold_2m_plus.csv`
- Top sale: **Gaspe House £83.2m**; biggest residential: **The Grove £38m**, **Le Vivier £17m**
- **Verified asking-vs-sold** for the headline residential sales — every one closed
  **below asking (≈6–15%)**:

  | Property | Asking | Sold | Δ | Agent |
  |---|---|---|---|---|
  | Gaspe House | OIEO £88.85m | £83.2m | −6.4% | (CBRE/Dandara) |
  | Le Vivier | £19.0m | £17.0m | −10.5% | Livingroom |
  | Eagle's Rest | £16.5m | £15.1m | −8.5% | Fine & Country |
  | Baymont House | £9.95m | £8.5m | −14.6% | Broadlands |
  | Clos de Coleron | £9.9m (orig £12.5m) | £8.5m | −14.1% | Savills |

  Plus brochures/listings for Maison d'Or, Le Val Lodge, Colline de Lavande,
  St. Mannelier, Beau Pré, The Grove. Full breakdown in **`REPORT.md`**.

## How it works

| Stage | Module | Source | Output |
|-------|--------|--------|--------|
| 1. Sold prices | `scrape_sold.py` | places.je **JSON API** (`?json=true`) | name, address, parish, ISO sale date, sale price, selling agent |
| 2. Cross-index | `enrich.py` | verified web-search findings + (opt) live + (opt) Wayback | asking price, discount %, brochure PDFs, first-listed date |

The places.je sold endpoint returns clean JSON when called with `?json=true`
(it 403s bot user-agents, so `http.py` sends a desktop-browser UA). Detail
pages are an ASP.NET/React app that embeds the property as inline hydrate JSON,
and the for-sale search API exposes `propertyId`, `price`, `estateAgent` and a
`publishedAt` first-listed date.

### Where asking prices / brochures come from

places.je publishes only the **sold** price (not the historical asking price),
removes a listing once sold, and **blocks crawlers** — so web archives barely
captured it (Wayback has sparse snapshots; Common Crawl has *none*). The asking
price therefore comes from the **agent's own marketing**: brochures (often on
Issuu or `assets.savills.com`) and listing pages carry the guide price. These
are found by **web search per property**.

Findings live in **`data/manual_search.json`**, keyed by `SoldProperty.key()`
(`name|date|price`), each entry: `asking_price`, `asking_price_display`,
`source`, `brochure_pdfs`, `first_listed_iso`, `notes`. `enrich.py` merges them,
computes discount % and days-on-market, and writes the enriched dataset. The
file shipped here was populated by searching the headline sales; extend it (by
hand or by automating a search backend) to cover more of the 985.

## Usage

```bash
python3 scripts/run.py scrape            # Stage 1: all £2m+ sold -> data/sold_2m_plus.{csv,json}
python3 scripts/run.py scrape --min-price 5000000 --max-pages 3
python3 scripts/run.py enrich            # Stage 2: merge findings -> data/sold_2m_plus_enriched.{csv,json}
python3 scripts/run.py enrich --live     # also flag current re-listings (see caveat)
python3 scripts/run.py enrich --wayback  # also probe Wayback Availability API for first-listed dates
python3 scripts/run.py probe             # report which archive backends are reachable here
```

## Optional sources & their caveats

- **`--live`** (flip detector): matches a sold property to a *currently on-market*
  places.je listing by distinctive house-name tokens. Matching is **identity-only —
  price/discount is never used**, so a home that sold 50% below asking is matched
  exactly like one that sold at asking (verified: live gaps span −89% to +17,100%,
  none filtered). But it reports a **present-day** asking price (not the sale-time
  asking), and generic house-names cause false positives, so treat it as a lead
  generator, not ground truth. Off by default.
- **`--wayback`**: `web.archive.org` (CDX + snapshot content) is blocked by egress
  in some sandboxes. The `archive.org` apex **Availability API** is usually still
  reachable and recovers a first-listed *date* (and an openable snapshot link)
  for any exact URL it can resolve — wired in as a fallback. Run `probe` to see
  what your environment can reach. Tested dead-ends: Common Crawl (no places.je
  coverage), arquivo.pt (none), archive.ph (403). The scraper does not evade the
  egress filter.

## Data captured per property

**Stage 1:** `name, address, parish, sale_date(+iso), sale_price(+display),
agent(+slug), source_page`.

**Stage 2 (`*_enriched`):** `asking_price(+display, +source), first_listed_iso(+source),
days_on_market, price_delta, price_delta_pct, brochure_pdfs, notes`.

## Project layout

```
jersey_props/
  config.py        # UA, URLs, price floor, delays, paths
  http.py          # stdlib GET with browser UA + retry/backoff
  models.py        # SoldProperty, EnrichedProperty dataclasses
  scrape_sold.py   # stage 1 — places.je sold JSON API
  places_live.py   # current-listings index (flip detector)
  wayback.py       # Wayback CDX + Availability API helpers
  enrich.py        # stage 2 — multi-source cross-index
  storage.py       # CSV / JSON persistence
scripts/run.py     # CLI: scrape | enrich | probe
data/              # sold_2m_plus.*, *_enriched.*, manual_search.json
REPORT.md          # generated analysis
```

## Etiquette / legal

Public transaction data for personal research; identifies as a normal browser
and throttles requests. Respect places.je's terms and don't hammer the site.
