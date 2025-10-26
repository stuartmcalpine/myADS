"""Main citation tracker class."""

import logging
from typing import Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from rich.console import Console
from rich.table import Table
from rich import box
import datetime

from myads import ADSQueryWrapper
from .constants import DEFAULT_DATABASE_PATH
from .database import DatabaseManager
from .models import Author, Publication, ADSToken
from .publications import PublicationManager
from .citations import CitationManager
from .reports import ReportGenerator
from .search import SearchManager

logger = logging.getLogger(__name__)


class CitationTracker:
    """Main class for tracking citations through the ADS API."""

    def __init__(
        self, database_path: Optional[str] = None, create_tables: bool = True
    ):
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
        self.console = Console()

        # Initialize database manager
        self.db_manager = DatabaseManager(self.database_path, create_tables)

        # Initialize ADS wrapper
        self._ads_wrapper = None

        # Initialize managers
        self.publication_manager = PublicationManager(
            self.console, lambda: self.ads_wrapper
        )
        self.citation_manager = CitationManager(
            self.console, lambda: self.ads_wrapper
        )
        self.report_generator = ReportGenerator(self.console)
        self.search_manager = SearchManager(self.console, lambda: self.ads_wrapper)

    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        return self.db_manager.session_scope()

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

    # Token operations
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

    # Author operations
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
                session.flush()

                self.console.print(
                    f"[green]Added author {forename} {surname} (ID: {author.id}).[/green]"
                )
                return author.id

            except IntegrityError as e:
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
                    .filter_by(author_id=author.id, ignored=False)
                    .scalar()
                )

                table.add_row(
                    str(author.id),
                    f"{author.forename} {author.surname}",
                    author.orcid or "-",
                    str(pub_count),
                )

            self.console.print(table)

    # Publication operations (delegate to PublicationManager)
    def ignore_publication(
        self, publication_id: int, reason: Optional[str] = None
    ) -> bool:
        """Mark a publication as ignored."""
        with self.session_scope() as session:
            return self.publication_manager.ignore_publication(
                session, publication_id, reason
            )

    def unignore_publication(self, publication_id: int) -> bool:
        """Unmark a publication as ignored."""
        with self.session_scope() as session:
            return self.publication_manager.unignore_publication(session, publication_id)

    def list_ignored_publications(self, author_id: Optional[int] = None) -> None:
        """Display a table of ignored publications."""
        with self.session_scope() as session:
            self.publication_manager.list_ignored_publications(session, author_id)

    def clear_rejected_papers(self, author_id: Optional[int] = None) -> int:
        """Clear rejected papers from deep check memory."""
        with self.session_scope() as session:
            return self.publication_manager.clear_rejected_papers(session, author_id)

    def list_rejected_papers(self, author_id: Optional[int] = None) -> None:
        """Display a table of rejected papers from deep check."""
        with self.session_scope() as session:
            self.publication_manager.list_rejected_papers(session, author_id)

    def fetch_author_publications(
        self, author_id: int, max_rows: int = 2000, deep: bool = False
    ):
        """Fetch publications for an author from ADS."""
        with self.session_scope() as session:
            return self.publication_manager.fetch_author_publications(
                session, author_id, max_rows, deep
            )

    # Citation operations (delegate to CitationManager)
    def check_citations(
        self,
        author_id: Optional[int] = None,
        max_rows: int = 2000,
        verbose: bool = False,
        deep: bool = False,
    ) -> Dict:
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
        deep : bool, optional
            Whether to perform deep check with name-only search.

        Returns
        -------
        Dict
            Nested dictionary of citation updates by author.
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
                self.console.print(
                    f"Checking citations for [cyan]{author.forename} {author.surname}[/cyan]..."
                )

                # Refresh author's publications first
                self.fetch_author_publications(author.id, max_rows, deep=deep)

                # Get the updated publications list (excluding ignored)
                publications = (
                    session.query(Publication)
                    .filter_by(author_id=author.id, ignored=False)
                    .all()
                )

                # Check citations
                author_results = self.citation_manager.check_citations(
                    session, publications, max_rows
                )

                if author_results:
                    results[author.id] = author_results
                    # Display results for this author
                    self.citation_manager.display_citation_results(
                        session, author, author_results, verbose
                    )

            if not results:
                self.console.print("[yellow]No new or updated citations found.[/yellow]")

        return results

    # Report operations (delegate to ReportGenerator)
    def generate_report(
        self, author_id: Optional[int] = None, show_ignored: bool = False
    ) -> None:
        """
        Generate a citation report for one or all authors.

        Parameters
        ----------
        author_id : int, optional
            ID of a specific author to report on. If None, report on all authors.
        show_ignored : bool, optional
            Whether to include ignored publications in the report.
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
                query = session.query(Publication).filter_by(author_id=author.id)

                if not show_ignored:
                    query = query.filter_by(ignored=False)

                publications = query.order_by(Publication.citation_count.desc()).all()

                self.report_generator.generate_author_report(
                    session, author, publications
                )

    # Search operations (delegate to SearchManager)
    def search_author_publications(
        self,
        surname: str,
        forename: str,
        orcid: Optional[str] = None,
        max_rows: int = 100,
        sort: str = "citation_count desc",
        output_format: str = "table",
        include_stats: bool = True,
        first_author_only: bool = False,
    ):
        """Search for an author's publications directly from ADS."""
        return self.search_manager.search_author_publications(
            surname,
            forename,
            orcid,
            max_rows,
            sort,
            output_format,
            include_stats,
            first_author_only,
        )
