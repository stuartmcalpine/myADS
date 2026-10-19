"""End-to-end tests of CitationTracker.check_citations with a mocked ADS layer."""

from unittest.mock import Mock

from myads.query import ADSQuery
from myads.cite_tracker.models import Citation, Publication
from myads.cite_tracker.tracker import CitationTracker


def _query(fl, docs):
    resp = Mock()
    resp.json.return_value = {
        "responseHeader": {"QTime": 1, "status": 0},
        "response": {"numFound": len(docs), "docs": docs},
    }
    return ADSQuery("q", fl, 2000, resp)


def _fake_wrapper():
    """ADS wrapper returning one paper per author and one citing paper (no DOI)."""
    wrapper = Mock()

    def get(q, fl, **kwargs):
        surname = "Doe" if "Doe" in q else "Roe"
        return _query(
            fl,
            [{
                "bibcode": f"2020{surname}",
                "title": [f"Paper by {surname}"],
                "author": [f"{surname}, Jane", "Other, A."],
                "citation_count": 1,
                "pubdate": "2020-01-00",
            }],
        )

    def citations(bibcode, fl, rows):
        return _query(
            fl,
            [{
                "bibcode": f"cite-{bibcode}",
                "title": ["Citing paper"],
                "author": ["Citer, A."],
                "date": "2024-01-01T00:00:00Z",
            }],
        )

    wrapper.get.side_effect = get
    wrapper.citations.side_effect = citations
    return wrapper


def test_check_citations_multiple_authors(temp_db):
    tracker = CitationTracker(database_path=temp_db)
    tracker._ads_wrapper = _fake_wrapper()
    tracker.add_author("Jane", "Doe")
    tracker.add_author("Jane", "Roe")

    results = tracker.check_citations()

    assert len(results) == 2
    with tracker.session_scope() as session:
        assert session.query(Publication).count() == 2
        assert session.query(Citation).count() == 2
        assert session.query(Citation).first().doi is None


def test_second_check_reports_no_changes(temp_db):
    """Missing fields (e.g. DOI) must not mark citations as updated every run."""
    tracker = CitationTracker(database_path=temp_db)
    tracker._ads_wrapper = _fake_wrapper()
    tracker.add_author("Jane", "Doe")

    tracker.check_citations()
    assert tracker.check_citations() == {}
