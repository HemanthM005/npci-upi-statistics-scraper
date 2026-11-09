"""Fetch raw monthly UPI statistics from the NPCI website.

Strategy
--------
1. **API-first** - NPCI's React front-end hydrates from a Strapi JSON API.
   Hitting that endpoint directly is fast, stable and kind to the server.
2. **Browser fallback** - if the API shape changes or the response is gated,
   render the public page with Playwright and parse the table from the DOM.

Both paths return the same intermediate shape: a list of dict rows with the
raw strings exactly as published, leaving all cleaning/typing to ``clean.py``.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ScraperConfig

logger = logging.getLogger(__name__)

RawRow = dict[str, Any]


def _build_session(cfg: ScraperConfig) -> requests.Session:
    """A session with sane retry/backoff so transient 5xx/429s self-heal."""
    session = requests.Session()
    retry = Retry(
        total=cfg.max_retries,
        backoff_factor=cfg.backoff_factor,
        status_forcelist=cfg.retry_statuses,
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": cfg.user_agent, "Accept": "application/json"})
    return session


# --------------------------------------------------------------------------- #
# Path 1: Strapi JSON API
# --------------------------------------------------------------------------- #
def fetch_via_api(cfg: ScraperConfig) -> list[RawRow] | None:
    """Try each candidate endpoint; return parsed rows from the first that works."""
    session = _build_session(cfg)
    for path in cfg.api_candidates:
        url = f"{cfg.base_url}{path}"
        logger.info("Trying API endpoint: %s", url)
        time.sleep(cfg.min_delay_seconds)
        try:
            resp = session.get(url, timeout=cfg.request_timeout)
        except requests.RequestException as exc:
            logger.warning("Request failed for %s: %s", url, exc)
            continue
        if resp.status_code != 200:
            logger.info("  -> %s returned HTTP %s", path, resp.status_code)
            continue
        try:
            payload = resp.json()
        except ValueError:
            logger.info("  -> %s did not return JSON", path)
            continue
        rows = _extract_rows_from_payload(payload)
        if rows:
            logger.info("  -> parsed %d rows from API", len(rows))
            return rows
    logger.info("No API endpoint yielded rows.")
    return None


def _extract_rows_from_payload(payload: dict[str, Any]) -> list[RawRow]:
    """Walk a Strapi payload and pull out anything that looks like a monthly row.

    Strapi nests the useful data under ``data.attributes.<something>`` and the
    exact key drifts between CMS revisions, so instead of hard-coding the path
    we recursively hunt for list-of-objects whose keys mention month/volume.
    """
    found: list[RawRow] = []

    MONTHISH = ("month", "period", "date")
    VALUEISH = ("volume", "value", "banks", "count", "amount")

    def looks_like_stat_row(obj: dict[str, Any]) -> bool:
        keys = {k.lower() for k in obj}
        return any(m in k for k in keys for m in MONTHISH) and any(
            v in k for k in keys for v in VALUEISH
        )

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            # Strapi wraps entities as {"attributes": {...}}; flatten that.
            if "attributes" in node and isinstance(node["attributes"], dict):
                walk(node["attributes"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            dict_items = [x for x in node if isinstance(x, dict)]
            if dict_items and all(looks_like_stat_row(x) for x in dict_items):
                found.extend(dict_items)
            else:
                for item in node:
                    walk(item)

    walk(payload)
    return found


# --------------------------------------------------------------------------- #
# Path 2: Browser fallback (Playwright)
# --------------------------------------------------------------------------- #
def fetch_via_browser(cfg: ScraperConfig) -> list[RawRow]:
    """Render the public page and parse the stats table from the live DOM.

    Used when the API path yields nothing. NPCI may present a captcha; with
    ``headless=False`` a human can solve it once and the table then renders.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Browser fallback needs Playwright. Install with:\n"
            "    pip install playwright && playwright install chromium"
        ) from exc

    rows: list[RawRow] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.headless)
        page = browser.new_page(user_agent=cfg.user_agent)
        logger.info("Opening %s in browser...", cfg.stats_page_url)
        page.goto(cfg.stats_page_url, timeout=cfg.browser_wait_ms)
        try:
            page.wait_for_selector("table tr td", timeout=cfg.browser_wait_ms)
        except Exception:
            logger.warning(
                "Stats table did not render in time "
                "(captcha unsolved or layout changed)."
            )
            browser.close()
            return rows

        headers = [
            h.inner_text().strip()
            for h in page.query_selector_all("table th")
        ] or list(cfg.expected_columns)

        for tr in page.query_selector_all("table tr"):
            cells = [td.inner_text().strip() for td in tr.query_selector_all("td")]
            if len(cells) >= 2:
                rows.append(dict(zip(headers, cells)))
        browser.close()
    logger.info("Parsed %d rows from rendered DOM.", len(rows))
    return rows


def scrape(cfg: ScraperConfig | None = None) -> list[RawRow]:
    """Public entrypoint: API-first, browser fallback, raw rows out."""
    cfg = cfg or ScraperConfig()
    rows = fetch_via_api(cfg)
    if rows:
        return rows
    if cfg.use_browser_fallback:
        logger.info("Falling back to browser rendering...")
        return fetch_via_browser(cfg)
    raise RuntimeError("API returned no rows and browser fallback is disabled.")
