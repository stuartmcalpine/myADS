"""Tests for database operations and models."""

import pytest
from myads.cite_tracker.database import DatabaseManager
from myads.cite_tracker.models import Author, Publication, Citation, RejectedPaper, ADSToken


def test_database_creation(temp_db):
    """Test that database is created with proper tables."""
    db = DatabaseManager(temp_db, create_tables=True)

    # Verify database file exists
    import os
    assert os.path.exists(temp_db)

    # Verify we can query (tables exist)
    with db.session_scope() as session:
        count = session.query(Author).count()
        assert count == 0


def test_add_author(temp_db):
    """Test adding an author to the database."""
    db = DatabaseManager(temp_db, create_tables=True)

    with db.session_scope() as session:
        author = Author(
            forename="Jane",
            surname="Doe",
            orcid="0000-0002-1825-0097"
        )
        session.add(author)
        session.commit()

        # Query back
        result = session.query(Author).filter_by(surname="Doe").first()
        assert result is not None
        assert result.forename == "Jane"
        assert result.orcid == "0000-0002-1825-0097"


def test_add_publication(temp_db):
    """Test adding a publication with author relationship."""
    db = DatabaseManager(temp_db, create_tables=True)

    with db.session_scope() as session:
        # Create author first
        author = Author(forename="John", surname="Smith")
        session.add(author)
        session.commit()

        # Add publication
        pub = Publication(
            bibcode="2023ApJ...123..456S",
            title="Test Paper",
            author_id=author.id,
            citation_count=10
        )
        session.add(pub)
        session.commit()

        # Verify
        result = session.query(Publication).filter_by(bibcode="2023ApJ...123..456S").first()
        assert result is not None
        assert result.title == "Test Paper"
        assert result.author.surname == "Smith"


def test_add_citation(temp_db):
    """Test adding citations to publications."""
    db = DatabaseManager(temp_db, create_tables=True)

    with db.session_scope() as session:
        # Create author and publication
        author = Author(forename="Alice", surname="Brown")
        session.add(author)
        session.commit()

        pub = Publication(
            bibcode="2023MNRAS.456..789B",
            title="Original Paper",
            author_id=author.id
        )
        session.add(pub)
        session.commit()

        # Add citation
        citation = Citation(
            bibcode="2024Natur.567..890C",
            title="Citing Paper",
            publication_id=pub.id
        )
        session.add(citation)
        session.commit()

        # Verify relationship
        result = session.query(Publication).filter_by(bibcode="2023MNRAS.456..789B").first()
        assert len(result.citations) == 1
        assert result.citations[0].bibcode == "2024Natur.567..890C"


def test_rejected_paper(temp_db):
    """Test rejected paper storage."""
    db = DatabaseManager(temp_db, create_tables=True)

    with db.session_scope() as session:
        author = Author(forename="Bob", surname="Jones")
        session.add(author)
        session.commit()

        rejected = RejectedPaper(
            bibcode="2023arXiv230112345J",
            author_id=author.id
        )
        session.add(rejected)
        session.commit()

        # Verify
        result = session.query(RejectedPaper).filter_by(author_id=author.id).first()
        assert result is not None
        assert result.bibcode == "2023arXiv230112345J"


def test_ads_token_storage(temp_db):
    """Test ADS token storage."""
    db = DatabaseManager(temp_db, create_tables=True)

    with db.session_scope() as session:
        token = ADSToken(token="test-token-12345")
        session.add(token)
        session.commit()

        # Verify
        result = session.query(ADSToken).first()
        assert result is not None
        assert result.token == "test-token-12345"


def test_cascade_delete_author(temp_db):
    """Test that deleting an author cascades to publications and rejected papers."""
    db = DatabaseManager(temp_db, create_tables=True)

    with db.session_scope() as session:
        # Create author with publication and rejected paper
        author = Author(forename="Charlie", surname="Davis")
        session.add(author)
        session.commit()

        pub = Publication(
            bibcode="2023Sci...789..012D",
            title="Paper",
            author_id=author.id
        )
        rejected = RejectedPaper(
            bibcode="2023arXiv234567890D",
            author_id=author.id
        )
        session.add(pub)
        session.add(rejected)
        session.commit()

        author_id = author.id

        # Delete author
        session.delete(author)
        session.commit()

        # Verify cascade
        assert session.query(Author).filter_by(id=author_id).first() is None
        assert session.query(Publication).filter_by(author_id=author_id).first() is None
        assert session.query(RejectedPaper).filter_by(author_id=author_id).first() is None


def test_unique_constraint_bibcode_author(temp_db):
    """Test that bibcode+author_id must be unique for publications."""
    from sqlalchemy.exc import IntegrityError

    db = DatabaseManager(temp_db, create_tables=True)

    # Add author and first publication
    with db.session_scope() as session:
        author = Author(forename="Eve", surname="Wilson")
        session.add(author)
        session.commit()

        pub1 = Publication(
            bibcode="2023ApJ...111..222W",
            title="First",
            author_id=author.id
        )
        session.add(pub1)
        session.commit()

    # Try to add duplicate in new session - should raise IntegrityError
    with pytest.raises(IntegrityError):
        with db.session_scope() as session:
            author = session.query(Author).first()
            pub2 = Publication(
                bibcode="2023ApJ...111..222W",
                title="Duplicate",
                author_id=author.id
            )
            session.add(pub2)
            session.commit()
