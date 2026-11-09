"""Scrape, clean and validate NPCI's monthly UPI product statistics."""
from .clean import clean
from .scraper import scrape
from .validate import validate

__all__ = ["scrape", "clean", "validate"]
__version__ = "1.0.0"
