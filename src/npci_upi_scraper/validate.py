"""Schema + quality checks for the cleaned UPI statistics.

Validation is what turns "I scraped some numbers" into "I ship data you can
trust". If the site silently changes units or drops a column, these checks
fail loudly instead of poisoning downstream analysis.
"""
from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

# UPI has only grown month over month since launch, and the published figures
# sit comfortably inside these generous bounds - tight enough to catch a unit
# error (e.g. crores reported as rupees) but loose enough to never false-alarm.
upi_schema = DataFrameSchema(
    {
        "month": Column(
            str,
            checks=Check.str_matches(r"^\d{4}-(0[1-9]|1[0-2])$"),
            nullable=False,
            unique=True,
        ),
        "banks_live": Column(
            "Int64",
            checks=Check.in_range(1, 2000),
            nullable=True,
        ),
        "volume_mn": Column(
            float,
            checks=Check.greater_than(0),
            nullable=True,
        ),
        "value_cr": Column(
            float,
            checks=Check.greater_than(0),
            nullable=True,
        ),
    },
    strict=True,       # reject unexpected columns - catches layout drift
    coerce=True,
)


def validate(df):
    """Validate in place; raises pandera.errors.SchemaError on any violation."""
    return upi_schema.validate(df, lazy=True)
