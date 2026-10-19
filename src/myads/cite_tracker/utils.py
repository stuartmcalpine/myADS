"""Shared helpers for the citation tracker."""

import datetime
from typing import Iterable, Optional

ADS_ABS_URL = "https://ui.adsabs.harvard.edu/abs"


def ads_link(bibcode: str) -> str:
    """Return the ADS abstract page URL for a bibcode."""
    return f"{ADS_ABS_URL}/{bibcode}/abstract"


def parse_ads_date(date_str: Optional[str]) -> Optional[datetime.datetime]:
    """
    Parse an ADS date string into a datetime.

    Handles ADS ``pubdate`` values such as "2021-03-00" (zero month/day are
    treated as 1) and ``date`` values such as "2021-03-01T00:00:00Z".

    Returns
    -------
    datetime or None
        Parsed date, or None if the string is empty or unparseable.
    """
    if not date_str:
        return None
    try:
        parts = date_str.split("T")[0].split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return datetime.datetime(year, month or 1, day or 1)
    except (ValueError, IndexError, TypeError, AttributeError):
        return None


def years_since(date: datetime.datetime) -> float:
    """Years elapsed since ``date``, floored at one month."""
    return max((datetime.datetime.now() - date).days / 365.25, 1 / 12.0)


def h_index(citation_counts: Iterable[Optional[int]]) -> int:
    """Compute the h-index from a collection of citation counts."""
    counts = sorted((c or 0 for c in citation_counts), reverse=True)
    return sum(1 for i, c in enumerate(counts) if c >= i + 1)


def ordinal(n: int) -> str:
    """Return the English ordinal for n (1st, 2nd, 3rd, 4th, 11th, 21st, ...)."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def truncate(text: Optional[str], length: int) -> str:
    """Truncate text to ``length`` characters, adding an ellipsis if cut."""
    text = text or ""
    return text if len(text) <= length else text[: length - 3] + "..."
