"""Turn raw scraped rows into a tidy, typed DataFrame.

The site publishes numbers with commas, stray whitespace and inconsistent
month labels ("Apr-24", "April 2024", "Apr 2024"). This module normalises all
of that into a single clean schema that downstream analysis can rely on.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

# Map many header spellings the site has used over the years onto our canon.
_COLUMN_ALIASES = {
    "month": "month",
    "period": "month",
    "no. of banks live on upi": "banks_live",
    "banks live on upi": "banks_live",
    "banks": "banks_live",
    "volume (in mn)": "volume_mn",
    "volume in mn": "volume_mn",
    "volume": "volume_mn",
    "value (in cr.)": "value_cr",
    "value (in cr)": "value_cr",
    "value in cr": "value_cr",
    "value": "value_cr",
}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _canon_key(key: str) -> str:
    k = re.sub(r"\s+", " ", str(key).strip().lower())
    return _COLUMN_ALIASES.get(k, k)


def _to_number(raw: Any) -> float | None:
    """'1,23,456.78' or '₹ 1,23,456' -> 123456.78 (handles Indian grouping)."""
    if raw is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(raw))
    if s in ("", "-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_month(raw: Any) -> str | None:
    """Normalise any month label to ISO 'YYYY-MM'."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    m = re.search(r"([a-z]{3,9})[^\d]*(\d{2,4})", s)
    if not m:
        return None
    mon_name, year = m.group(1)[:3], m.group(2)
    if mon_name not in _MONTHS:
        return None
    year_i = int(year)
    if year_i < 100:                       # 24 -> 2024
        year_i += 2000
    return f"{year_i:04d}-{_MONTHS[mon_name]:02d}"


def clean(raw_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Raw scraped dicts -> tidy, typed, de-duplicated DataFrame."""
    normalised: list[dict[str, Any]] = []
    for row in raw_rows:
        rec = {_canon_key(k): v for k, v in row.items()}
        normalised.append(
            {
                "month": _parse_month(rec.get("month")),
                "banks_live": _to_number(rec.get("banks_live")),
                "volume_mn": _to_number(rec.get("volume_mn")),
                "value_cr": _to_number(rec.get("value_cr")),
            }
        )

    df = pd.DataFrame(normalised, columns=["month", "banks_live", "volume_mn", "value_cr"])
    df = df.dropna(subset=["month"]).drop_duplicates(subset=["month"])
    df = df.sort_values("month").reset_index(drop=True)

    # Integer-valued columns look cleaner as nullable ints.
    for col in ("banks_live",):
        df[col] = df[col].astype("Int64")

    return df
