"""Tests for CLI functionality."""

import pytest
from myads.cite_tracker.tracker import CitationTracker


def test_tracker_initialization(temp_db):
    """Test that tracker can be initialized."""
    tracker = CitationTracker(database_path=temp_db)
    assert tracker.database_path == temp_db


def test_add_author_basic(temp_db):
    """Test adding an author via tracker."""
    tracker = CitationTracker(database_path=temp_db)

    result = tracker.add_author(
        forename="Test",
        surname="Author",
        orcid="0000-0001-2345-6789"
    )

    # Returns author ID (integer)
    assert isinstance(result, int)
    assert result > 0

    # Verify author was added
    with tracker.session_scope() as session:
        from myads.cite_tracker.models import Author
        author = session.query(Author).filter_by(surname="Author").first()
        assert author is not None
        assert author.forename == "Test"
        assert author.orcid == "0000-0001-2345-6789"


def test_add_duplicate_author(temp_db):
    """Test that adding duplicate author returns existing ID."""
    tracker = CitationTracker(database_path=temp_db)

    # Add first author
    first_id = tracker.add_author("Jane", "Doe", "0000-0001-1111-1111")

    # Try to add duplicate - should return same ID
    second_id = tracker.add_author("Jane", "Doe", "0000-0001-1111-1111")
    assert second_id == first_id


def test_remove_author(temp_db):
    """Test removing an author."""
    tracker = CitationTracker(database_path=temp_db)

    # Add author
    tracker.add_author("Remove", "Me")

    # Get author ID
    with tracker.session_scope() as session:
        from myads.cite_tracker.models import Author
        author = session.query(Author).filter_by(surname="Me").first()
        author_id = author.id

    # Remove author
    result = tracker.remove_author(author_id)
    assert result is True

    # Verify removed
    with tracker.session_scope() as session:
        from myads.cite_tracker.models import Author
        author = session.query(Author).filter_by(id=author_id).first()
        assert author is None


def test_remove_nonexistent_author(temp_db):
    """Test removing author that doesn't exist."""
    tracker = CitationTracker(database_path=temp_db)

    result = tracker.remove_author(999)
    assert result is False


def test_add_token(temp_db):
    """Test adding ADS API token."""
    tracker = CitationTracker(database_path=temp_db)

    # add_ads_token doesn't return a value
    tracker.add_ads_token("test-token-abc123")

    # Verify token was stored
    with tracker.session_scope() as session:
        from myads.cite_tracker.models import ADSToken
        token = session.query(ADSToken).first()
        assert token is not None
        assert token.token == "test-token-abc123"


def test_ignore_publication(temp_db):
    """Test ignoring a publication."""
    tracker = CitationTracker(database_path=temp_db)

    # Add author and publication
    tracker.add_author("Test", "User")

    with tracker.session_scope() as session:
        from myads.cite_tracker.models import Author, Publication
        author = session.query(Author).first()

        pub = Publication(
            bibcode="2023TEST.123..456U",
            title="Test Publication",
            author_id=author.id
        )
        session.add(pub)
        session.commit()
        pub_id = pub.id

    # Ignore the publication
    result = tracker.ignore_publication(pub_id, reason="Testing ignore")
    assert result is True

    # Verify it's ignored
    with tracker.session_scope() as session:
        from myads.cite_tracker.models import Publication
        pub = session.query(Publication).filter_by(id=pub_id).first()
        assert pub.ignored is True
        assert pub.ignore_reason == "Testing ignore"


def test_unignore_publication(temp_db):
    """Test unignoring a publication."""
    tracker = CitationTracker(database_path=temp_db)

    # Add author and ignored publication
    tracker.add_author("Test", "User")

    with tracker.session_scope() as session:
        from myads.cite_tracker.models import Author, Publication
        author = session.query(Author).first()

        pub = Publication(
            bibcode="2023TEST.789..012U",
            title="Ignored Publication",
            author_id=author.id,
            ignored=True,
            ignore_reason="Initial ignore"
        )
        session.add(pub)
        session.commit()
        pub_id = pub.id

    # Unignore
    result = tracker.unignore_publication(pub_id)
    assert result is True

    # Verify it's unignored
    with tracker.session_scope() as session:
        from myads.cite_tracker.models import Publication
        pub = session.query(Publication).filter_by(id=pub_id).first()
        assert pub.ignored is False
        assert pub.ignore_reason is None


def test_custom_database_path(temp_db):
    """Test that custom database path is respected."""
    custom_path = temp_db.replace(".db", "_custom.db")

    tracker = CitationTracker(database_path=custom_path)
    assert tracker.database_path == custom_path

    # Verify database is created at custom location
    import os
    tracker.add_author("Test", "Custom")
    assert os.path.exists(custom_path)

    # Cleanup
    if os.path.exists(custom_path):
        os.unlink(custom_path)
