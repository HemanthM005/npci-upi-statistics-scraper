"""Configuration for the NPCI UPI statistics scraper.

All tunable knobs live here so the scraper stays easy to point at a new
endpoint or run politely against the live site.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# NPCI serves its site as a React SPA backed by a Strapi CMS. The monthly
# UPI numbers are rendered client-side from a JSON endpoint rather than being
# present in the initial HTML, so the "fast path" talks to that API directly
# and the "fallback path" renders the page with a real browser.
BASE_URL = "https://www.npci.org.in"

# Candidate Strapi content endpoints, tried in order. The live slug changes
# occasionally when NPCI reorganises its CMS, so we probe a small ordered list
# instead of hard-coding one and breaking on the next redesign.
API_ENDPOINT_CANDIDATES = (
    "/api/upi-product-statistics?populate=deep",
    "/api/product-statistics?filters[product][$eq]=upi&populate=deep",
    "/api/ecosystem-statistics-page?populate=deep",
)

# Public page used by the browser fallback.
STATS_PAGE_URL = f"{BASE_URL}/what-we-do/upi/product-statistics"


@dataclass(frozen=True)
class ScraperConfig:
    base_url: str = BASE_URL
    stats_page_url: str = STATS_PAGE_URL
    api_candidates: tuple[str, ...] = API_ENDPOINT_CANDIDATES

    # Politeness / resilience
    user_agent: str = (
        "npci-upi-statistics-scraper/1.0 "
        "(+https://github.com/HemanthM005/npci-upi-statistics-scraper)"
    )
    request_timeout: int = 30
    max_retries: int = 4
    backoff_factor: float = 1.5          # exponential backoff between retries
    min_delay_seconds: float = 1.0       # polite gap between requests
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)

    # Browser fallback
    use_browser_fallback: bool = True
    headless: bool = False               # NPCI gates data behind a captcha;
                                         # a headed browser lets a human solve it
    browser_wait_ms: int = 20_000        # max wait for the table to render

    expected_columns: tuple[str, ...] = field(
        default=("month", "banks_live", "volume_mn", "value_cr")
    )
