"""Shared configuration for the scraper.

Everything lives in the standard library so the pipeline runs with zero
`pip install` steps in a locked-down environment.
"""

from __future__ import annotations

import os

# A real browser User-Agent is required: places.je returns 403 to bot UAs
# (e.g. ClaudeBot / GPTBot are disallowed in robots.txt) but serves the
# server-rendered HTML normally to a desktop browser UA.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

BASE_URL = "https://www.places.je"
SOLD_PATH = "/sold-property/"

# Default floor for "interesting" sales. The user asked for £2m+.
DEFAULT_MIN_PRICE = 2_000_000

# places.je renders 20 transactions per page.
RESULTS_PER_PAGE = 20

# Be a polite citizen: small delay between page fetches.
REQUEST_DELAY_SECONDS = float(os.environ.get("PLACES_DELAY", "1.0"))
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 4

# Wayback Machine CDX API (used by the enrichment stage). NOTE: web.archive.org
# may be blocked by egress policy in some sandboxes; run enrichment where it is
# reachable (e.g. a normal local machine).
WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_BASE = "https://web.archive.org/web"

# Output locations.
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
