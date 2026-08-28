# Open Weights Index

A second, self-contained dataset in this repo: the **machine-format Hugging Face
model card** for the current release of every open-weights model, joined to its
**Artificial Analysis Intelligence Index** score.

Same house rules as the property scraper — **standard library only**, no
`pip install`, Python 3.10+.

## Output

| File | What it is |
|------|------------|
| `data/model_cards/<org>__<name>.json` | One raw card per model: the Hub's `/api/models/<repo>?full=true` document, the YAML front matter of the card README, and the repo's `config.json` |
| `data/open_model_index.json` | The joined table, plus provenance and the list of models skipped for want of a readable card |
| `data/open_model_index.csv` | The same table, flat, for spreadsheets |
| `site/open_models.html` | Self-contained sortable/filterable page built from the JSON |

## Running it

```sh
python3 scripts/build_model_index.py     # fetch cards + scores -> data/
python3 scripts/build_model_table.py     # data/ -> site/open_models.html
```

`--no-cards` reuses the archived cards instead of re-fetching the Hub;
`--limit N` stops after N models.

## Where the numbers come from

**Model cards.** A card on the Hub is a README whose YAML front matter is the
machine-readable half. The Hub also exposes that metadata — plus facts the front
matter does not carry, such as parameter counts summed from the safetensors
index — through `/api/models/<repo>?full=true`. Both are pulled, so parameter
totals are the shipped weights rather than a rounded marketing figure.

**Intelligence Index.** Artificial Analysis gates its API behind a key, but every
model detail page on `artificialanalysis.ai` server-renders the whole catalogue
into its React Server Components payload — one flat JSON object per model with
the index score, its nine component evaluations, licence, parameter counts and
the Hugging Face URL the weights live at. `open_models/artificial_analysis.py`
reassembles that payload from the page's `self.__next_f.push([1,"…"])` chunks
and reads the objects straight out of it. That last field is what makes the join
to the Hub reliable: the pairing is the benchmarker's own, not a name match.

## What "latest version" means here

Applied in order, in `open_models/index.py`:

1. **Candidates** are open-weights entries that are not marked deprecated and
   were released on or after `config.RELEASED_SINCE`. An entry also qualifies
   when it already points at a public Hub repo — a lab's weights sometimes land
   before Artificial Analysis re-classifies the entry (GLM-5.3 on this run).
2. **Reasoning-effort variants** of one release (`max`, `high`, `low`,
   `Non-reasoning`) collapse into a single row, scored at its best setting; the
   spread is kept alongside and shown in the page's detail panel. Keying on lab
   plus base name rather than on the repo also merges releases split across a
   base and an `-it` repo.
3. **Superseded releases drop out**: a release goes when the same lab has a newer
   one in the same size class scoring at least as well. What remains is each
   lab's live lineup across size tiers, rather than only the newest thing each
   lab shipped.

Anything with no readable card — gated behind a licence click, or moved — is
skipped and named in `skipped` in the JSON and at the foot of the page.

## Known joins that need a hand

`config.HF_REPO_OVERRIDES` maps a handful of model slugs onto the first-party
repo carrying the card, where Artificial Analysis links a lab's own download page
or a quantised mirror instead. Licence labels prefer the card over the index,
since a card that declares `license: other` and names a bespoke licence is
authoritative for its own repo.
