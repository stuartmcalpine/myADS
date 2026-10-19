"""Tests for citation tracker helpers and report formatting."""

import datetime

import pytest
from rich.console import Console

from myads.cite_tracker.reports import ReportGenerator
from myads.cite_tracker.utils import h_index, ordinal, parse_ads_date, truncate


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2021-03-00", datetime.datetime(2021, 3, 1)),
        ("2021-00-00", datetime.datetime(2021, 1, 1)),
        ("2021-03-15T00:00:00Z", datetime.datetime(2021, 3, 15)),
        ("2021", datetime.datetime(2021, 1, 1)),
        ("", None),
        (None, None),
        ("garbage", None),
    ],
)
def test_parse_ads_date(value, expected):
    assert parse_ads_date(value) == expected


def test_h_index():
    assert h_index([]) == 0
    assert h_index([10, 8, 5, 4, 3]) == 4
    assert h_index([0, None, 1]) == 1


@pytest.mark.parametrize(
    "n,expected",
    [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"),
     (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"), (103, "103rd")],
)
def test_ordinal(n, expected):
    assert ordinal(n) == expected


def test_truncate():
    assert truncate("short", 10) == "short"
    assert truncate("a" * 20, 10) == "a" * 7 + "..."
    assert truncate(None, 10) == ""


def test_author_position_requires_exact_surname():
    report = ReportGenerator(Console())
    authors = "Williams, A.; Lin, B.; Li, Chen"
    assert report._find_author_position(authors, "Li", "Chen") == "3rd"


def test_author_position_checks_initial():
    report = ReportGenerator(Console())
    authors = "Smith, A.; Smith, J."
    assert report._find_author_position(authors, "Smith", "John") == "2nd"
    assert report._find_author_position(authors, "Jones", "John") == "?"
