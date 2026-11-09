# NPCI UPI Statistics Scraper

A small, production-shaped pipeline that scrapes **India's monthly UPI product
statistics** from the [NPCI website](https://www.npci.org.in/what-we-do/upi/product-statistics),
cleans the messy published figures into a tidy dataset, and **validates** it
before anything is written to disk.

UPI processes **10+ billion transactions a month** — but NPCI only publishes the
numbers as a chart on a JavaScript-rendered page, with no download button. This
project turns that into a clean, analysis-ready CSV, updated with one command.

```
month,banks_live,volume_mn,value_cr
2024-03,555,13441000,1978000
2024-04,560,13304000,1978500
...
```

---

## Why this is harder than it looks

The page is a **React single-page app backed by a Strapi CMS**, so the data
isn't in the HTML — it's fetched as JSON and rendered client-side, behind a
captcha. A naive `requests.get()` returns an empty shell. This scraper handles
it with a two-tier strategy:

| Tier | How | When it's used |
|------|-----|----------------|
| **1. API-first** | Talks to the Strapi JSON endpoint directly and walks the nested payload to find the monthly rows | Default — fast, stable, light on the server |
| **2. Browser fallback** | Renders the real page with Playwright, lets a human clear the captcha once, then parses the table from the live DOM | When the API shape changes or the response is gated |

Because the CMS slug drifts between site redesigns, the API tier **probes an
ordered list of candidate endpoints** and **recursively discovers** the stats
rows by shape (keys that look like `month` + `volume`/`value`) rather than
hard-coding a fragile path.

## Architecture

```
scrape()                clean()                 validate()
  │                        │                        │
  ├─ fetch_via_api ──┐     ├─ normalise headers     ├─ pandera schema
  │   (requests +    │     ├─ parse Indian-format   │   • month = YYYY-MM, unique
  │    retry/backoff)│     │   numbers (1,23,456)    │   • volume/value > 0
  │                  ├──►  ├─ canonicalise months   ├─ strict=True rejects
  └─ fetch_via_browser│    │   (Apr-24 → 2024-04)    │   unexpected columns
      (Playwright)   ┘     └─ de-dup + sort          └─ fails LOUD on drift
        raw rows          tidy DataFrame             trusted CSV
```

Separation of concerns is deliberate: scraping, cleaning and validation are
independent and independently testable. If NPCI changes units tomorrow, the
**validation layer fails the run instead of silently shipping bad data.**

## Install

```bash
git clone https://github.com/HemanthM005/npci-upi-statistics-scraper
cd npci-upi-statistics-scraper
pip install -r requirements.txt
# optional, for the browser fallback:
playwright install chromium
```

## Usage

```bash
# API-first; falls back to a (headed) browser if needed
python -m npci_upi_scraper --out data/upi_monthly.csv

# API only, no browser
python -m npci_upi_scraper --no-browser --out data/upi_monthly.csv

# verbose logging
python -m npci_upi_scraper -v
```

Or from Python:

```python
from npci_upi_scraper import scrape, clean, validate

df = validate(clean(scrape()))
df.to_csv("upi_monthly.csv", index=False)
```

## Output schema

| column | type | description |
|--------|------|-------------|
| `month` | `str` | reporting month, ISO `YYYY-MM` |
| `banks_live` | `Int64` | number of banks live on UPI |
| `volume_mn` | `float` | transaction volume, millions |
| `value_cr` | `float` | transaction value, ₹ crore |

> `data/sample_output/upi_monthly_SAMPLE.csv` is an **illustrative** sample
> showing the output schema. Run the scraper to fetch the live figures.

## Tests

```bash
pip install pytest
PYTHONPATH=src pytest -q
```

The suite covers the fragile bits: Indian-format number parsing, month
normalisation across label styles, de-duplication, and schema validation.

## Tech

Python · requests (retry/backoff) · Playwright · pandas · pandera

## Responsible scraping

Targets only **publicly published** aggregate statistics, sends a descriptive
User-Agent, rate-limits requests, and retries politely with exponential
backoff. No personal data; no authentication bypass.

## License

MIT © 2026 Manikala Hemanth
