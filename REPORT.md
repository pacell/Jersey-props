# Jersey £2m+ sold-property analysis

_Generated 2026-06-14 from places.je. **985 transactions** >= £2,000,000, total **£4,139,052,738** (mean £4,202,083)._

A companion mobile web app lives in `site/` (filterable table + map). Asking prices, brochures and key metrics were recovered for the high-value sales (all of the last 12 months researched via web search; see `data/manual_search.json`).

## Asking vs sold — biggest discounts to launch guide

| Property | Launch asking | Sold | Δ | Agent |
|---|---|---|---|---|
| Clos de Coleron, St. Brelade | £15,000,000 (orig 2022; cut to | £8,500,000 | -43.3% | Savills |
| Le Coin, 1 Le Coin Cottages and 2  | £19,000,000 (orig F&C guide) | £12,000,000 | -36.8% | Fine & Country |
| Tides Reach, St. Brelade | £3,550,000 | £2,400,000 | -32.4% | Savills |
| Hotel Savoy, St. Helier | £6,250,000 (commercial guide) | £4,500,000 | -28.0% | — |
| Trelawney, St. Brelade | £3,995,000 | £3,005,000 | -24.8% | — |
| La Solitude Farm, St. Lawrence | £3,950,000 | £3,150,000 | -20.3% | Gaudin & Co |
| Le Val Lodge (formerly Sea View Ho | £16,250,000 | £13,000,000 | -20.0% | Broadlands |
| La Cachette, St. Peter | £2,350,000 | £2,000,000 | -14.9% | Livingroom |
| Baymont House (formerly called Siv | £9,950,000 | £8,500,000 | -14.6% | Broadlands |
| Malorey House (formerly known as L | £4,950,000 | £4,250,000 | -14.1% | — |
| Les Ruelles (formerly ‘Burfield’ a | £2,850,000 | £2,460,000 | -13.7% | Savills |
| St. Mannelier with the Cottage, St | £12,950,000 | £11,492,500 | -11.3% | Savills |
| Amberley, | £4,650,000 | £4,150,000 | -10.8% | Fine & Country |
| St. Peter’s House, | £8,950,000 | £8,000,000 | -10.6% | Fine & Country |
| LE VIVIER | £19,000,000 | £17,000,000 | -10.5% | Livingroom |
| Maison Icho, St. Clement | £2,450,000 (orig; cut to £2.35 | £2,200,000 | -10.2% | — |
| Haut du Mont Farm (formerly Haut d | £7,250,000 | £6,525,000 | -10.0% | — |
| Coline de Lavande (formerly ‘Wildw | £35,000,000 (original guide) | £31,500,000 | -10.0% | Savills |

## Sold OVER asking
| Property | Asking | Sold | Δ |
|---|---|---|---|
| Little Orchard, | £1,995,000 | £2,250,000 | +12.8% |

_Asking price recovered for 32 sales; 24 have brochures. Discounts are vs the original launch guide where known._

## Top 12 sales
| Sale | Date | Property | Agent |
|---|---|---|---|
| £83,200,000 | 2025-02-28 | Gaspe House | — |
| £66,133,332 | 2018-04-20 | La Croute | — |
| £38,000,000 | 2025-12-05 | The Grove, St. Lawrence | Fine & Country |
| £36,200,000 | 2025-02-28 | 27 – 28 Esplanade and 3 La Rue des Mielles | — |
| £31,500,000 | 2025-04-04 | Coline de Lavande (formerly ‘Wildwaysʼ) | Savills |
| £31,100,109 | 2021-03-26 | EDEN HOUSE (formerly known as 'Travers Far | — |
| £27,000,000 | 2015-01-16 | A certain commercial office building with  | — |
| £26,012,200 | 2006-11-01 | De Gruchy's Department Store | — |
| £21,500,000 | 2022-06-24 | Maison d'Or | — |
| £21,500,000 | 2017-10-27 | De Gruchy's Department Store | — |
| £18,987,000 | 2010-07-01 | Queensway House | — |
| £18,625,000 | 2015-02-27 | Firstly, a certain house known as Daisy Hi | — |

## Transactions by year
| Year | Count |
|---|---|
| 2026 | 32 |
| 2025 | 68 |
| 2024 | 58 |
| 2023 | 45 |
| 2022 | 84 |
| 2021 | 105 |
| 2020 | 54 |
| 2019 | 39 |
| 2018 | 50 |
| 2017 | 53 |
| 2016 | 44 |
| 2015 | 31 |
| 2014 | 37 |
| 2013 | 18 |
| 2012 | 19 |
| 2011 | 17 |
| 2010 | 23 |
| 2009 | 28 |
| 2008 | 23 |
| 2007 | 50 |
| 2006 | 26 |
| 2005 | 19 |
| 2004 | 15 |
| 2003 | 12 |
| 2002 | 21 |
| 2001 | 14 |

## Method & caveats

- **Sold prices**: places.je JSON API (authoritative; the only public price).
- **Asking/brochures**: agent listings & brochures via web search (places.je removes sold listings and Jersey has no open price register). Deepest discounts measured vs the *launch* guide.
- **Map**: Nominatim road+parish geocoding (bounds-checked to Jersey) with parish-centroid fallback.
- **Not captured**: undisclosed-price trophy deals never enter places.je (e.g. Maison de la Valette, £39.95m->£32m->undisclosed). Commercial lots (offices, hotels, share transfers) rarely have public guides.

