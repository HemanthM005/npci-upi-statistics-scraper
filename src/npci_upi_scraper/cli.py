"""Command-line entrypoint: scrape -> clean -> validate -> write CSV.

    python -m npci_upi_scraper --out data/upi_monthly.csv
"""
from __future__ import annotations

import argparse
import logging
import sys

from .clean import clean
from .config import ScraperConfig
from .scraper import scrape
from .validate import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape NPCI monthly UPI statistics.")
    parser.add_argument("--out", default="data/upi_monthly.csv", help="output CSV path")
    parser.add_argument("--no-browser", action="store_true", help="disable browser fallback")
    parser.add_argument("--headless", action="store_true", help="run browser headless")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = ScraperConfig(
        use_browser_fallback=not args.no_browser,
        headless=args.headless,
    )

    logging.info("Scraping NPCI UPI statistics...")
    raw = scrape(cfg)
    if not raw:
        logging.error("No data scraped. Exiting.")
        return 1

    df = clean(raw)
    logging.info("Cleaned %d monthly records (%s .. %s).",
                 len(df), df["month"].min(), df["month"].max())

    try:
        validate(df)
    except Exception as exc:  # pandera raises a rich SchemaErrors here
        logging.error("Validation FAILED - not writing output.\n%s", exc)
        return 2

    df.to_csv(args.out, index=False)
    logging.info("Validated & wrote %d rows -> %s", len(df), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
