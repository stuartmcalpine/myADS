"""Database models for the citation tracker."""

import datetime
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for declarative class definitions."""

    pass


class Author(Base):
    """Authors we are tracking in the citation system."""

    __tablename__ = "authors"

    id = Column(Integer, primary_key=True)
    forename = Column(String(50), nullable=False)
    surname = Column(String(50), nullable=False)
    orcid = Column(String(50))

    # Relationships
    publications = relationship(
        "Publication", back_populates="author", cascade="all, delete-orphan"
    )
    rejected_papers = relationship(
        "RejectedPaper", back_populates="author", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "forename", "surname", "orcid", name="uq_forename_surname_orcid"
        ),
    )

    def __repr__(self) -> str:
        """String representation of the author."""
        return f"Author({self.forename} {self.surname}, ORCID: {self.orcid})"


class Publication(Base):
    """Publications by tracked authors."""

    __tablename__ = "publications"

    id = Column(Integer, primary_key=True)
    bibcode = Column(String(50), nullable=False)
    title = Column(String, nullable=False)
    pubdate = Column(String(50))
    authors = Column(Text)  # Store full author list as comma-separated string
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False)
    citation_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.datetime.now)
    ignored = Column(Boolean, default=False)
    ignore_reason = Column(Text)

    # Relationships
    author = relationship("Author", back_populates="publications")
    citations = relationship(
        "Citation", back_populates="publication", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("bibcode", "author_id", name="uq_pub_bibcode_author"),
    )

    def __repr__(self) -> str:
        """String representation of the publication."""
        return f"Publication({self.title}, {self.bibcode})"


class Citation(Base):
    """Citations to tracked publications."""

    __tablename__ = "citations"

    id = Column(Integer, primary_key=True)
    bibcode = Column(String(50), nullable=False)
    title = Column(String, nullable=False)
    authors = Column(String)
    publication_date = Column(String(50))
    doi = Column(String(100))
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=False)
    discovery_date = Column(DateTime, default=datetime.datetime.now)

    # Relationships
    publication = relationship("Publication", back_populates="citations")

    __table_args__ = (
        UniqueConstraint("bibcode", "publication_id", name="uq_citation_bibcode_pub"),
    )

    def __repr__(self) -> str:
        """String representation of the citation."""
        return f"Citation({self.title}, {self.bibcode})"


class RejectedPaper(Base):
    """Papers that were rejected during deep check."""

    __tablename__ = "rejected_papers"

    id = Column(Integer, primary_key=True)
    bibcode = Column(String(50), nullable=False)
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False)
    rejected_date = Column(DateTime, default=datetime.datetime.now)

    # Relationships
    author = relationship("Author", back_populates="rejected_papers")

    __table_args__ = (
        UniqueConstraint("bibcode", "author_id", name="uq_rejected_bibcode_author"),
    )

    def __repr__(self) -> str:
        """String representation of the rejected paper."""
        return f"RejectedPaper({self.bibcode})"


class ADSToken(Base):
    """ADS API token storage."""

    __tablename__ = "ads_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    added_date = Column(DateTime, default=datetime.datetime.now)

    def __repr__(self) -> str:
        """String representation of the token."""
        return f"ADSToken(added: {self.added_date})"
