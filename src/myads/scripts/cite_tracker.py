from typing import Dict, List, Optional, Tuple, Union, Any
import os
import pandas as pd
import logging
from dataclasses import dataclass
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from tabulate import tabulate
import datetime
from myads import ADSQueryWrapper, ADSQuery, ADSPaper
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box
from contextlib import contextmanager

# Set up logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_DATABASE_PATH = os.path.join(Path.home(), "myADS_database.db")


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
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False)
    citation_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.datetime.now)

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


class ADSToken(Base):
    """ADS API token storage."""

    __tablename__ = "ads_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    added_date = Column(DateTime, default=datetime.datetime.now)

    def __repr__(self) -> str:
        """String representation of the token."""
        return f"ADSToken(added: {self.added_date})"


@dataclass
class CitationUpdate:
    """Data class to hold citation update information."""

    new_citations: List[Citation]
    updated_citations: List[Citation]


class CitationTracker:
    """Main class for tracking citations through the ADS API."""

    def __init__(self, database_path: Optional[str] = None, create_tables: bool = True):
        """
        Initialize the citation tracker.

        Parameters
        ----------
        database_path : str, optional
            Path to the SQLite database file.
        create_tables : bool, optional
            Whether to create tables if they don't exist.
        """
        self.database_path = database_path or DEFAULT_DATABASE_PATH
        self.engine = create_engine(f"sqlite:///{self.database_path}")
        self.Session = sessionmaker(bind=self.engine)
        self.console = Console()

        # Create tables if needed
        if create_tables:
            Base.metadata.create_all(self.engine)

        # Initialize ADS wrapper
        self._ads_wrapper = None

    @contextmanager
    def session_scope(self) -> Session:
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def __enter__(self) -> "CitationTracker":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        pass

    @property
    def ads_wrapper(self) -> ADSQueryWrapper:
        """
        Get the ADS wrapper, initializing it if necessary.

        Returns
        -------
        ADSQueryWrapper
            Initialized ADS API wrapper.

        Raises
        ------
        ValueError
            If no ADS token is found in the database.
        """
        if self._ads_wrapper is None:
            token = self.get_ads_token()
            if not token:
                raise ValueError(
                    "No ADS token found. Please add a token with add_ads_token()."
                )
            self._ads_wrapper = ADSQueryWrapper(token)
        return self._ads_wrapper

    def add_ads_token(self, token: str) -> None:
        """
        Add or update the ADS API token.

        Parameters
        ----------
        token : str
            The ADS API token.
        """
        with self.session_scope() as session:
            existing_token = session.query(ADSToken).first()

            if existing_token:
                existing_token.token = token
                existing_token.added_date = datetime.datetime.now()
            else:
                session.add(ADSToken(token=token))

            session.commit()
            self.console.print(f"[green]ADS token updated successfully.[/green]")

        # Reset the ADS wrapper to use the new token
        self._ads_wrapper = None

    def get_ads_token(self) -> Optional[str]:
        """
        Get the ADS API token from the database.

        Returns
        -------
        str or None
            The ADS API token if found, None otherwise.
        """
        with self.session_scope() as session:
            token_record = session.query(ADSToken).first()
            return token_record.token if token_record else None

    def add_author(
        self,
        forename: str,
        surname: str,
        orcid: Optional[str] = None,
    ) -> int:
        """
        Add a new author to track.

        Parameters
        ----------
        forename : str
            Author's first name.
        surname : str
            Author's last name.
        orcid : str, optional
            Author's ORCID identifier.

        Returns
        -------
        int
            ID of the new or existing author.

        Raises
        ------
        IntegrityError
            If there is a database constraint violation.
        """
        with self.session_scope() as session:
            try:
                # Check if author already exists
                existing_author = (
                    session.query(Author)
                    .filter_by(forename=forename, surname=surname, orcid=orcid)
                    .first()
                )

                if existing_author:
                    self.console.print(
                        f"[yellow]Author {forename} {surname} already exists (ID: {existing_author.id}).[/yellow]"
                    )
                    return existing_author.id

                # Add new author
                author = Author(
                    forename=forename,
                    surname=surname,
                    orcid=orcid,
                )
                session.add(author)
                session.commit()

                self.console.print(
                    f"[green]Added author {forename} {surname} (ID: {author.id}).[/green]"
                )
                return author.id

            except IntegrityError as e:
                session.rollback()
                logger.error(f"Database error adding author: {e}")
                self.console.print(f"[red]Error adding author: {e}[/red]")
                raise

    def remove_author(self, author_id: int) -> bool:
        """
        Remove an author and all their associated data.

        Parameters
        ----------
        author_id : int
            ID of the author to remove.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        with self.session_scope() as session:
            author = session.query(Author).filter_by(id=author_id).first()

            if not author:
                self.console.print(
                    f"[yellow]No author found with ID {author_id}.[/yellow]"
                )
                return False

            author_name = f"{author.forename} {author.surname}"
            session.delete(author)
            session.commit()

            self.console.print(
                f"[green]Removed author {author_name} and all associated data.[/green]"
            )
            return True

    def list_authors(self) -> None:
        """Display a table of all tracked authors."""
        with self.session_scope() as session:
            authors = session.query(Author).all()

            if not authors:
                self.console.print("[yellow]No authors found in the database.[/yellow]")
                return

            table = Table(title="Tracked Authors", box=box.ROUNDED)
            table.add_column("ID", justify="right", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("ORCID", style="blue")
            table.add_column("Publications", justify="right", style="magenta")

            for author in authors:
                pub_count = (
                    session.query(func.count(Publication.id))
                    .filter_by(author_id=author.id)
                    .scalar()
                )

                table.add_row(
                    str(author.id),
                    f"{author.forename} {author.surname}",
                    author.orcid or "-",
                    str(pub_count),
                )

            self.console.print(table)

    def fetch_author_publications(
        self, author_id: int, max_rows: int = 2000
    ) -> List[Publication]:
        """
        Fetch publications for an author from ADS.

        Parameters
        ----------
        author_id : int
            ID of the author to fetch publications for.
        max_rows : int, optional
            Maximum number of publications to fetch.

        Returns
        -------
        List[Publication]
            List of publications for the author.

        Raises
        ------
        ValueError
            If the author is not found.
        """
        with self.session_scope() as session:
            author = session.query(Author).filter_by(id=author_id).first()

            if not author:
                raise ValueError(f"No author found with ID {author_id}")

            # Build the query string
            if author.orcid:
                q = (
                    f"orcid_pub:{author.orcid} OR orcid_user:{author.orcid} OR "
                    f'orcid_other:{author.orcid} OR first_author:"{author.surname}, {author.forename}"'
                )
            else:
                q = f'first_author:"{author.surname}, {author.forename}"'

            # Fields to retrieve
            fl = "title,bibcode,author,citation_count,pubdate"

            # Query ADS
            data = self.ads_wrapper.get(
                q=q, fl=fl, rows=max_rows, sort="pubdate desc", verbose=False
            )

            if data is None or data.num_found == 0:
                self.console.print(
                    f"[yellow]No publications found for {author.forename} {author.surname}.[/yellow]"
                )
                return []

            session.commit()

            return self._update_publications(session, author, data)

    def _update_publications(
        self, session: Session, author: Author, data: ADSQuery
    ) -> List[Publication]:
        """
        Update the publications for an author in the database.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        author : Author
            Author object.
        data : ADSQuery
            Query results from ADS API.

        Returns
        -------
        List[Publication]
            List of updated or new publications.
        """
        updated_pubs = []

        for paper in data.papers:
            # Check if publication exists
            pub = (
                session.query(Publication)
                .filter_by(bibcode=paper.bibcode, author_id=author.id)
                .first()
            )

            if pub:
                # Update existing publication
                pub.title = paper.title
                pub.citation_count = getattr(paper, "citation_count", 0)
                pub.pubdate = getattr(paper, "pubdate", None)
                pub.last_updated = datetime.datetime.now()
            else:
                # Add new publication
                pub = Publication(
                    bibcode=paper.bibcode,
                    title=paper.title,
                    pubdate=getattr(paper, "pubdate", None),
                    citation_count=getattr(paper, "citation_count", 0),
                    author_id=author.id,
                    last_updated=datetime.datetime.now(),
                )
                session.add(pub)

            updated_pubs.append(pub)

        session.commit()
        return updated_pubs

    def check_citations(
        self,
        author_id: Optional[int] = None,
        max_rows: int = 2000,
        verbose: bool = False,
    ) -> Dict[int, Dict[str, CitationUpdate]]:
        """
        Check for new citations to tracked publications.

        Parameters
        ----------
        author_id : int, optional
            ID of a specific author to check. If None, check all authors.
        max_rows : int, optional
            Maximum number of publications to fetch per query.
        verbose : bool, optional
            Whether to print detailed output.

        Returns
        -------
        Dict[int, Dict[str, CitationUpdate]]
            Nested dictionary of citation updates by author and publication.
        """
        results = {}

        with self.session_scope() as session:
            # Determine which authors to check
            if author_id:
                authors = session.query(Author).filter_by(id=author_id).all()
            else:
                authors = session.query(Author).all()

            if not authors:
                self.console.print(
                    "[yellow]No authors found to check citations for.[/yellow]"
                )
                return results

            # Check each author
            for author in authors:
                author_results = {}
                self.console.print(
                    f"Checking citations for [cyan]{author.forename} {author.surname}[/cyan]..."
                )

                # Refresh author's publications first
                self.fetch_author_publications(author.id, max_rows)

                # Get the updated publications
                publications = (
                    session.query(Publication).filter_by(author_id=author.id).all()
                )

                # Check citations for each publication
                for pub in publications:
                    citation_data = self.ads_wrapper.citations(
                        pub.bibcode,
                        fl="title,bibcode,author,date,doi,citation_count",
                        rows=max_rows,
                    )

                    if citation_data and citation_data.num_found > 0:
                        citation_update = self._process_citations(
                            session, pub, citation_data
                        )
                        if (
                            citation_update.new_citations
                            or citation_update.updated_citations
                        ):
                            author_results[pub.bibcode] = citation_update

                if author_results:
                    results[author.id] = author_results

            # Display the results
            self._display_citation_results(session, results, verbose)

            session.commit()

        return results

    def _process_citations(
        self, session: Session, publication: Publication, citation_data: ADSQuery
    ) -> CitationUpdate:
        """
        Process citations for a publication.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        publication : Publication
            Publication to process citations for.
        citation_data : ADSQuery
            Citation data from ADS API.

        Returns
        -------
        CitationUpdate
            Object containing new and updated citations.
        """
        new_citations = []
        updated_citations = []

        for paper in citation_data.papers:
            # Check if citation exists
            citation = (
                session.query(Citation)
                .filter_by(bibcode=paper.bibcode, publication_id=publication.id)
                .first()
            )

            if citation:
                # Check if any fields need updating
                updated = False

                if citation.title != paper.title:
                    citation.title = paper.title
                    updated = True

                if hasattr(paper, "author") and str(citation.authors) != str(
                    paper.author
                ):
                    citation.authors = str(paper.author)
                    updated = True

                if hasattr(paper, "date") and citation.publication_date != paper.date:
                    citation.publication_date = paper.date
                    updated = True

                if hasattr(paper, "doi"):
                    doi_value = paper.doi
                    # Convert list to string if needed
                    if isinstance(doi_value, list):
                        doi_value = ";".join(doi_value)

                    if citation.doi != doi_value:
                        citation.doi = doi_value
                        updated = True

                if updated:
                    updated_citations.append(citation)
            else:
                # Create new citation
                doi_value = getattr(paper, "doi", None)
                # Convert list of DOIs to a string by joining with a separator
                if isinstance(doi_value, list):
                    doi_value = ";".join(doi_value)

                citation = Citation(
                    bibcode=paper.bibcode,
                    title=paper.title,
                    authors=str(getattr(paper, "author", [])),
                    publication_date=getattr(paper, "date", None),
                    doi=doi_value,  # Now this will be a string
                    publication_id=publication.id,
                    discovery_date=datetime.datetime.now(),
                )
                session.add(citation)
                new_citations.append(citation)

        # Update the publication's citation count
        publication.citation_count = len(citation_data.papers_dict.get("bibcode", []))
        publication.last_updated = datetime.datetime.now()

        session.commit()
        return CitationUpdate(
            new_citations=new_citations, updated_citations=updated_citations
        )

    def _display_citation_results(
        self,
        session,
        results: Dict[int, Dict[str, CitationUpdate]],
        verbose: bool = False,
    ) -> None:
        """
        Display the results of citation checks.

        Parameters
        ----------
        results : Dict[int, Dict[str, CitationUpdate]]
            Results from check_citations.
        verbose : bool, optional
            Whether to display detailed information.
        """
        if not results:
            self.console.print("[yellow]No new or updated citations found.[/yellow]")
            return

        for author_id, author_results in results.items():
            author = session.query(Author).filter_by(id=author_id).first()
            if not author:
                continue

            author_name = f"{author.forename} {author.surname}"

            for bibcode, citation_update in author_results.items():
                publication = (
                    session.query(Publication)
                    .filter_by(bibcode=bibcode, author_id=author_id)
                    .first()
                )

                if not publication:
                    continue

                # Display new citations
                if citation_update.new_citations:
                    self._print_citation_table(
                        author_name,
                        publication.title,
                        citation_update.new_citations,
                        "New",
                    )

                # Display updated citations if verbose
                if verbose and citation_update.updated_citations:
                    self._print_citation_table(
                        author_name,
                        publication.title,
                        citation_update.updated_citations,
                        "Updated",
                    )

    def _print_citation_table(
        self,
        author_name: str,
        publication_title: str,
        citations: List[Citation],
        citation_type: str,
    ) -> None:
        """
        Print a table of citations.

        Parameters
        ----------
        author_name : str
            Name of the author.
        publication_title : str
            Title of the publication.
        citations : List[Citation]
            List of citations to display.
        citation_type : str
            Type of citations (e.g., "New", "Updated").
        """
        title_color = "green" if citation_type == "New" else "blue"

        self.console.print(
            f"\n[bold {title_color}]{citation_type} citations for paper by {author_name}:[/bold {title_color}]"
        )
        self.console.print(f"[yellow]Title:[/yellow] {publication_title}")

        table = Table(box=box.ROUNDED)
        table.add_column("Title", style="cyan", no_wrap=False)
        table.add_column("Authors", style="green", no_wrap=False)
        table.add_column("Date", style="yellow")
        table.add_column("Link", style="blue")

        for citation in citations:
            # Truncate title if too long
            title = citation.title
            if len(title) > 60:
                title = title[:57] + "..."

            # Format authors
            authors = citation.authors
            if authors and len(authors) > 50:
                # Get first author and indicate there are more
                if isinstance(authors, str) and "," in authors:
                    authors = authors.split(",")[0] + ", et al."
                else:
                    authors = str(authors)[:47] + "..."

            # Create ADS link
            ads_link = f"https://ui.adsabs.harvard.edu/abs/{citation.bibcode}/abstract"

            # Format date
            date = citation.publication_date
            if date and len(date) > 10:
                date = date[:10]

            table.add_row(title, authors, date or "-", ads_link)

        self.console.print(table)

    def generate_report(self, author_id: Optional[int] = None) -> None:
        """
        Generate a citation report for one or all authors.

        Parameters
        ----------
        author_id : int, optional
            ID of a specific author to report on. If None, report on all authors.
        """
        with self.session_scope() as session:
            # Determine which authors to report on
            if author_id:
                authors = session.query(Author).filter_by(id=author_id).all()
            else:
                authors = session.query(Author).all()

            if not authors:
                self.console.print(
                    "[yellow]No authors found to generate reports for.[/yellow]"
                )
                return

            # Generate report for each author
            for author in authors:
                self._generate_author_report(session, author)

    def _generate_author_report(self, session: Session, author: Author) -> None:
        """
        Generate a citation report for a specific author.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        author : Author
            Author to generate report for.
        """
        publications = (
            session.query(Publication)
            .filter_by(author_id=author.id)
            .order_by(Publication.citation_count.desc())
            .all()
        )

        if not publications:
            self.console.print(
                f"[yellow]No publications found for {author.forename} {author.surname}.[/yellow]"
            )
            return

        self.console.print(
            f"\n[bold]Citation Report for [cyan]{author.forename} {author.surname}[/cyan][/bold]"
        )

        table = Table(
            title="Publications by Citation Count",
            box=box.ROUNDED,
            row_styles=["dim", ""],
        )
        table.add_column("Title", style="cyan", no_wrap=False)
        table.add_column(
            "Citations\n(last 90 days)\n\[per year]", justify="right", style="green"
        )
        table.add_column("Date", style="yellow")
        table.add_column("ADS Link", style="blue")

        total_citations = 0
        total_publications = len(publications)

        for pub in publications:
            # Get recent citations (last 90 days)
            ninety_days_ago = datetime.datetime.now() - datetime.timedelta(days=90)
            recent_citations = (
                session.query(func.count(Citation.id))
                .filter_by(publication_id=pub.id)
                .filter(Citation.publication_date.isnot(None))
                .filter(Citation.publication_date >= ninety_days_ago)
                .scalar()
            )

            # Create ADS link
            ads_link = f"https://ui.adsabs.harvard.edu/abs/{pub.bibcode}/abstract"

            # Calculate years since publication
            if pub.pubdate:
                try:
                    year = int(pub.pubdate.split("-")[0])
                    month = int(pub.pubdate.split("-")[1]) if "-" in pub.pubdate else 1
                    pub_date = datetime.datetime(year, month, 1)
                    years_since_pub = (datetime.datetime.now() - pub_date).days / 365.25
                    years_since_pub = max(years_since_pub, 1 / 12)
                except Exception:
                    years_since_pub = None
            else:
                years_since_pub = None

            # Calculate citations per year
            if years_since_pub:
                citations_per_year = pub.citation_count / years_since_pub
            else:
                citations_per_year = 0.0

            # Format title
            title = pub.title
            if len(title) > 60:
                title = title[:57] + "..."

            table.add_row(
                title,
                f"{pub.citation_count} ({recent_citations}) [{citations_per_year:.1f}]",
                pub.pubdate or "-",
                ads_link,
            )

            total_citations += pub.citation_count

        self.console.print(table)

        # Summary statistics
        self.console.print(f"\n[bold]Summary Statistics:[/bold]")
        self.console.print(f"Total Publications: [green]{total_publications}[/green]")
        self.console.print(f"Total Citations: [green]{total_citations}[/green]")

        if total_publications > 0:
            avg_citations = total_citations / total_publications
            self.console.print(
                f"Average Citations per Publication: [green]{avg_citations:.2f}[/green]"
            )

            # H-index calculation
            citation_counts = sorted(
                [p.citation_count for p in publications], reverse=True
            )
            h_index = 0
            for i, citations in enumerate(citation_counts, 1):
                if citations >= i:
                    h_index = i
                else:
                    break

            self.console.print(f"H-index: [green]{h_index}[/green]")


# Command-line interface functions


def add_author_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for adding an author."""
    tracker.add_author(
        forename=args["forename"],
        surname=args["surname"],
        orcid=args.get("orcid"),
    )


def remove_author_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for removing an author."""
    tracker.remove_author(args["author_id"])


def list_authors_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for listing authors."""
    tracker.list_authors()


def add_token_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for adding an ADS token."""
    tracker.add_ads_token(args["token"])


def check_citations_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for checking citations."""
    tracker.check_citations(
        author_id=args.get("author_id"),
        max_rows=args.get("max_rows", 2000),
        verbose=args.get("verbose", False),
    )


def generate_report_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for generating reports."""
    tracker.generate_report(author_id=args.get("author_id"))


def main():
    """Main entry point for the citation tracker CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="ADS Citation Tracker")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Add author command
    add_author_parser = subparsers.add_parser(
        "add-author", help="Add an author to track"
    )
    add_author_parser.add_argument("forename", help="Author first name")
    add_author_parser.add_argument("surname", help="Author last name")
    add_author_parser.add_argument("--orcid", help="Author ORCID identifier")

    # Remove author command
    remove_author_parser = subparsers.add_parser(
        "remove-author", help="Remove an author"
    )
    remove_author_parser.add_argument("author_id", type=int, help="Author ID to remove")

    # List authors command
    subparsers.add_parser("list-authors", help="List all tracked authors")

    # Add token command
    add_token_parser = subparsers.add_parser("add-token", help="Add ADS API token")
    add_token_parser.add_argument("token", help="ADS API token")

    # Check citations command
    check_parser = subparsers.add_parser("check", help="Check for new citations")
    check_parser.add_argument(
        "--author-id", type=int, help="Author ID to check (default: all authors)"
    )
    check_parser.add_argument(
        "--max-rows", type=int, default=2000, help="Maximum rows to return"
    )
    check_parser.add_argument(
        "--verbose", action="store_true", help="Show detailed output"
    )

    # Generate report command
    report_parser = subparsers.add_parser("report", help="Generate citation report")
    report_parser.add_argument(
        "--author-id", type=int, help="Author ID to report on (default: all authors)"
    )

    # Parse arguments
    args = parser.parse_args()

    # Create tracker
    tracker = CitationTracker()

    # Run command
    if args.command == "add-author":
        add_author_cli(tracker, vars(args))
    elif args.command == "remove-author":
        remove_author_cli(tracker, vars(args))
    elif args.command == "list-authors":
        list_authors_cli(tracker, vars(args))
    elif args.command == "add-token":
        add_token_cli(tracker, vars(args))
    elif args.command == "check":
        check_citations_cli(tracker, vars(args))
    elif args.command == "report":
        generate_report_cli(tracker, vars(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
