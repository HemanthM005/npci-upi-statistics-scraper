"""Unit tests for the cleaning layer - the part most likely to break silently."""
from __future__ import annotations

import pandas as pd

from npci_upi_scraper.clean import _parse_month, _to_number, clean
from npci_upi_scraper.validate import validate


def test_parse_month_variants():
    assert _parse_month("Apr-24") == "2024-04"
    assert _parse_month("April 2024") == "2024-04"
    assert _parse_month("Apr 2024") == "2024-04"
    assert _parse_month("Dec-2023") == "2023-12"
    assert _parse_month("garbage") is None


def test_to_number_indian_grouping():
    assert _to_number("1,23,456") == 123456.0
    assert _to_number("₹ 12,345.67") == 12345.67
    assert _to_number("-") is None
    assert _to_number(None) is None


def test_clean_dedupes_and_sorts():
    raw = [
        {"Month": "Apr-24", "Banks": "550", "Volume (in Mn)": "13,30,456", "Value (in Cr.)": "19,78,543"},
        {"Month": "Mar-24", "Banks": "545", "Volume (in Mn)": "13,44,100", "Value (in Cr.)": "19,78,000"},
        {"Month": "Apr-24", "Banks": "550", "Volume (in Mn)": "13,30,456", "Value (in Cr.)": "19,78,543"},  # dup
    ]
    df = clean(raw)
    assert list(df["month"]) == ["2024-03", "2024-04"]      # sorted, de-duped
    assert df.loc[df["month"] == "2024-04", "banks_live"].iloc[0] == 550


def test_cleaned_frame_passes_validation():
    raw = [
        {"Month": "Jan-24", "Banks": "500", "Volume (in Mn)": "12,20,000", "Value (in Cr.)": "18,40,000"},
        {"Month": "Feb-24", "Banks": "520", "Volume (in Mn)": "12,10,000", "Value (in Cr.)": "18,30,000"},
    ]
    validated = validate(clean(raw))
    assert isinstance(validated, pd.DataFrame)
    assert len(validated) == 2
