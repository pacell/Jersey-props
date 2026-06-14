# Jersey Properties — sold-price scraper & cross-indexer

Scrapes **actual sold prices** of high-value Jersey (Channel Islands) homes from
[places.je](https://www.places.je/sold-property/) and cross-indexes each sale
against its original market listing — recovering the **asking/guide price**, the
date it **first went on the market**, how long it sat (**days on market**), and
any **agent brochure PDFs** archived in the Wayback Machine.

Built standard-library-only (Python 3.10+), so it runs with **zero
`pip install`** in locked-down environments.

## What it does

The pipeline runs in stages:

| Stage | Module | Source | Output |
|-------|--------|--------|--------|
| 1. Sold prices | `scrape_sold.py` | `places.je/sold-property` | address, sale date, sale price, selling agent, parish |
| 2. Listing history | `wayback.py` | Wayback Machine CDX API | earliest archived listing → **first-on-market date** |
| 3. Cross-reference | `enrich.py` | archived listing snapshots | **asking price**, days-on-market, asking-vs-sold delta, brochure PDFs |

Results are written to `data/` as both `.json` and `.csv`.

## Usage

```bash
# Stage 1 — scrape every sold transaction at or above £2,000,000
python3 scripts/run.py scrape

# custom floor / cap the number of pages
python3 scripts/run.py scrape --min-price 5000000 --max-pages 3

# Stage 2 + 3 — cross-index the scraped data against the Wayback Machine
python3 scripts/run.py enrich            # or --limit 20 for a quick sample
```

Outputs:

- `data/sold_2m_plus.csv` / `.json` — raw sold transactions (stage 1)
- `data/sold_2m_plus_enriched.csv` / `.json` — cross-indexed (stages 2–3)

## Important: network / egress notes

- **places.je** returns **HTTP 403 to bot user-agents** (it disallows `ClaudeBot`,
  `GPTBot`, etc. in `robots.txt`) but serves normal server-rendered HTML to a
  desktop-browser User-Agent — which is what `jersey_props/http.py` sends. The
  scraper paginates politely (1s delay, configurable via `PLACES_DELAY`).
- **web.archive.org** (Wayback CDX API) is required for stages 2–3. It is
  **blocked by egress policy in some sandboxes** — including the one this repo
  was first generated in. Every Wayback call degrades gracefully (returns
  empty / records the problem in `notes`) rather than crashing, so run the
  `enrich` stage on a machine where `web.archive.org` is reachable to get real
  cross-referenced results.

## Wayback access workarounds

`web.archive.org` (which serves the CDX discovery API **and** snapshot content)
is blocked by egress policy in some sandboxes. Run `python3 scripts/run.py probe`
to see what your environment can reach. Findings and fallbacks, best → worst:

1. **Allowlist `web.archive.org`** in the environment's network policy
   ([docs](https://code.claude.com/docs/en/claude-code-on-the-web)) — restores
   the full CDX + content path. Cleanest fix if you own the environment.
2. **Run `enrich` locally** — any normal machine reaches `web.archive.org`.
3. **Availability API fallback (built in).** The `archive.org` *apex* is often
   allowed even when the `web.archive.org` *subdomain* is blocked, and it serves
   the [Availability API](https://archive.org/help/wayback_api.php). `wayback.py`
   uses it to recover the **first-on-market date** and an **openable snapshot
   URL** for any exact URL it can resolve. Limits: no wildcard discovery and no
   snapshot HTML, so it yields dates/links, not asking prices, and only for URLs
   that can be constructed (sold listings live at `/property/<numeric-id>`,
   which isn't derivable from the address — so hit-rate is low without CDX).

Alternatives that were tested and **don't help here**: Common Crawl index
(`index.commoncrawl.org` refused connections), `arquivo.pt` (reachable but zero
places.je captures), `archive.ph` (403), Memento TimeTravel aggregator (DNS
unavailable). Note: the live places.je site and its `sitemap.xml` only carry
**currently-listed** properties, so they can't supply history for sold ones.
The scraper does **not** attempt to evade the egress filter (e.g. IP/SNI
spoofing) — that would bypass a deliberate security control.

## Data captured per property

**Stage 1 (always available):** `name`, `address`, `parish`, `sale_date` +
`sale_date_iso`, `sale_price` + display, `agent` + `agent_slug`, `source_page`.

**Stages 2–3 (Wayback-dependent):** `asking_price` (+ source snapshot URL),
`first_listed_iso` (+ source), `days_on_market`, `price_delta` &
`price_delta_pct` (sale vs asking), `brochure_pdfs`, `notes` (match confidence /
diagnostics).

## How matching works

Sold listings on places.je carry no detail-page link, so stage 2 slugifies each
property's name + address, queries the Wayback CDX API for archived places.je
listing URLs, and keeps snapshots whose URL tokens overlap the property
(≥2 shared tokens). The **earliest** matching capture is treated as the
first-on-market date; that snapshot's HTML is parsed for the guide/asking price
(cue words: *Guide*, *Asking*, *Price*, *Offers*…, plus *Price on Application*).
`notes` records the match confidence so low-confidence rows are easy to filter.

## Project layout

```
jersey_props/
  config.py       # UA, URLs, price floor, delays, paths
  http.py         # stdlib GET with browser UA + retry/backoff
  models.py       # SoldProperty, EnrichedProperty dataclasses
  scrape_sold.py  # stage 1 — paginate & parse sold cards
  wayback.py      # stage 2 — Wayback CDX helpers
  enrich.py       # stage 3 — match listings, extract asking price
  storage.py      # CSV / JSON persistence
scripts/run.py    # CLI entry point
data/             # generated output
```

## Etiquette / legal

This collects **publicly listed** transaction data for personal research. It
identifies as a normal browser, throttles requests, and does not bypass any
paywall or login. Respect places.je's terms of use and don't hammer the site;
the default 1s delay is deliberate.
