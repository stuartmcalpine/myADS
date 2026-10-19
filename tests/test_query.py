"""Tests for the ADS query layer (no real API calls)."""

from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from myads import ADSQueryWrapper


def _response(docs, num_found=None, status_code=200):
    """Build a fake requests.Response for an ADS search."""
    resp = Mock()
    resp.status_code = status_code
    resp.headers = {"X-RateLimit-Remaining": "4999"}
    resp.text = ""
    resp.json.return_value = {
        "responseHeader": {"QTime": 1, "status": 0},
        "response": {
            "numFound": len(docs) if num_found is None else num_found,
            "docs": docs,
        },
    }
    return resp


def test_get_counts_one_api_call_per_request(mock_ads_token):
    wrapper = ADSQueryWrapper(mock_ads_token)
    with patch("myads.query.requests.get", return_value=_response([])) as get:
        wrapper.get("q", "bibcode")
    assert get.call_count == 1
    assert wrapper.ads_api_calls == 1


def test_get_does_not_multiply_retries(mock_ads_token):
    wrapper = ADSQueryWrapper(mock_ads_token, max_attempts=3)
    with patch(
        "myads.query.requests.get", return_value=_response([], status_code=500)
    ) as get, patch("myads.query.time.sleep"):
        with pytest.raises(RuntimeError):
            wrapper.get("q", "bibcode")
    assert get.call_count == 3


def test_get_all_results_uses_correct_offsets(mock_ads_token):
    """The final, shorter page must start where the previous page ended."""
    wrapper = ADSQueryWrapper(mock_ads_token)
    wrapper.MAX_ROWS_PER_QUERY = 3
    all_docs = [{"bibcode": f"b{i}"} for i in range(7)]

    def fake_get(url, **kwargs):
        params = parse_qs(urlparse(url).query)
        start, rows = int(params["start"][0]), int(params["rows"][0])
        return _response(all_docs[start : start + rows], num_found=len(all_docs))

    with patch("myads.query.requests.get", side_effect=fake_get):
        pages = wrapper.get_all_results("q", "bibcode")

    bibcodes = [p.bibcode for page in pages for p in page.papers]
    assert bibcodes == [d["bibcode"] for d in all_docs]


def test_missing_fields_are_none_on_papers(mock_ads_token):
    wrapper = ADSQueryWrapper(mock_ads_token)
    docs = [{"bibcode": "b1", "title": ["A title"]}]
    with patch("myads.query.requests.get", return_value=_response(docs)):
        result = wrapper.get("q", "bibcode,title,doi")

    (paper,) = result.papers
    assert paper.title == "A title"
    assert paper.doi is None
