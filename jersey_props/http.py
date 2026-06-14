"""Tiny stdlib HTTP helper with a browser UA, retries and backoff."""

from __future__ import annotations

import gzip
import time
import urllib.error
import urllib.request
from typing import Optional

from . import config


def fetch(url: str, *, timeout: int = config.REQUEST_TIMEOUT_SECONDS,
          retries: int = config.MAX_RETRIES) -> Optional[str]:
    """GET a URL and return decoded text, or None on persistent failure.

    Retries with exponential backoff (2s, 4s, 8s, 16s) on transient errors.
    """
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip",
    }
    delay = 2.0
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            last_err = e
            # 404/403 won't fix themselves with a retry; bail fast.
            if e.code in (403, 404, 410):
                return None
        except Exception as e:  # noqa: BLE001 - network errors of many kinds
            last_err = e
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    print(f"  ! giving up on {url}: {last_err}")
    return None
