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
from rich.prompt import Confirm # Added import
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

            # session.commit() is handled by session_scope
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
                # session.commit() will be called by session_scope, need to flush to get ID
                session.flush() 

                self.console.print(
                    f"[green]Added author {forename} {surname} (ID: {author.id}).[/green]"
                )
                return author.id

            except IntegrityError as e:
                # session.rollback() handled by session_scope
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
            # session.commit() handled by session_scope

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
        Fetch publications for an author from ADS, update local DB,
        and optionally remove local-only entries.
        """
        with self.session_scope() as session:
            author = session.query(Author).filter_by(id=author_id).first()

            if not author:
                self.console.print(f"[yellow]No author found with ID {author_id} for fetching publications.[/yellow]")
                raise ValueError(f"No author found with ID {author_id}")

            # 1. Get locally stored publications for this author BEFORE fetching from ADS
            local_pubs_before_fetch = (
                session.query(Publication).filter_by(author_id=author.id).all()
            )
            local_bibcodes_before_fetch = {p.bibcode for p in local_pubs_before_fetch}

            # Build the ADS query string
            if author.orcid:
                q = (
                    f"orcid_pub:{author.orcid} OR orcid_user:{author.orcid} OR "
                    f'orcid_other:{author.orcid} OR first_author:"{author.surname}, {author.forename}"'
                )
            else:
                q = f'first_author:"{author.surname}, {author.forename}"'
            
            fl = "title,bibcode,author,citation_count,pubdate"

            # Query ADS
            ads_api_results = self.ads_wrapper.get(
                q=q, fl=fl, rows=max_rows, sort="pubdate desc", verbose=False
            )

            current_ads_papers_list = [] # List of ADSPaper objects
            ads_bibcodes_from_api = set()

            if ads_api_results and ads_api_results.papers:
                try:
                    # Consume the generator from ads_api_results.papers if it is one
                    current_ads_papers_list = list(ads_api_results.papers)
                    ads_bibcodes_from_api = {p.bibcode for p in current_ads_papers_list if hasattr(p, 'bibcode')}
                except TypeError: # If it's already a list or not a generator
                    if ads_api_results.papers: # Ensure it's not None
                         current_ads_papers_list = ads_api_results.papers
                         ads_bibcodes_from_api = {p.bibcode for p in current_ads_papers_list if hasattr(p, 'bibcode')}


            if not ads_api_results or ads_api_results.num_found == 0:
                self.console.print(
                    f"[yellow]No publications found in ADS for {author.forename} {author.surname}.[/yellow]"
                )
                # If ADS returns nothing, all local papers for this author are candidates for removal.

            # 2. Identify local publications not found in current ADS results
            bibcodes_to_check_for_removal = local_bibcodes_before_fetch - ads_bibcodes_from_api

            if bibcodes_to_check_for_removal:
                self.console.print(
                    f"\n[bold yellow]Checking for local publications not found in current ADS results for {author.forename} {author.surname}:[/bold yellow]"
                )
                for bibcode_to_remove in bibcodes_to_check_for_removal:
                    pub_to_remove = next(
                        (p for p in local_pubs_before_fetch if p.bibcode == bibcode_to_remove), None
                    )
                    if pub_to_remove:
                        display_title = pub_to_remove.title
                        if len(display_title) > 70:
                            display_title = display_title[:67] + "..."
                        
                        self.console.print(f"Local entry: [cyan]{display_title}[/cyan] (Bibcode: {pub_to_remove.bibcode})")
                        
                        if not self.console.is_interactive:
                            self.console.print(
                                "[yellow]Non-interactive mode. Skipping removal prompt. Entry will be kept.[/yellow]"
                            )
                            continue # Skip to the next bibcode to check

                        confirmation = Confirm.ask(
                            f"This entry was not found in the latest ADS results for this author. Remove it from your local database?",
                            default=False, # Default to No for safety
                        )
                        if confirmation:
                            self.console.print(
                                f"[red]Removing {pub_to_remove.bibcode} ('{display_title}') from local database.[/red]"
                            )
                            session.delete(pub_to_remove)
                        else:
                            self.console.print(
                                f"[green]Keeping {pub_to_remove.bibcode} ('{display_title}') in local database.[/green]"
                            )
            
            # 3. Update local database with current ADS publications
            # This will add new papers from ADS or update existing ones.
            self._update_publications(session, author, current_ads_papers_list)

            # session.commit() is handled by the session_scope context manager.
            
            # Return the final list of publications for this author from the DB
            # after potential removals, updates, and additions.
            final_author_pubs_in_db = (
                session.query(Publication).filter_by(author_id=author.id).all()
            )
            return final_author_pubs_in_db

    def _update_publications(
        self, session: Session, author: Author, current_ads_papers: List[ADSPaper]
    ) -> List[Publication]:
        """
        Update the publications for an author in the database based on a list of ADSPaper objects.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        author : Author
            Author object.
        current_ads_papers : List[ADSPaper]
            List of ADSPaper objects fetched from ADS.

        Returns
        -------
        List[Publication]
            List of updated or new SQLAlchemy Publication objects.
        """
        updated_sqlalchemy_pubs = []

        for paper_obj in current_ads_papers:  # paper_obj is an ADSPaper instance
            # Check if publication exists
            pub = (
                session.query(Publication)
                .filter_by(bibcode=paper_obj.bibcode, author_id=author.id)
                .first()
            )
    
            try:
                cite_count = int(getattr(paper_obj, "citation_count", 0) or 0)
            except:
                cite_count = 0

            if pub:
                # Update existing publication
                pub.title = paper_obj.title
                pub.citation_count = cite_count
                pub.pubdate = getattr(paper_obj, "pubdate", None)
                pub.last_updated = datetime.datetime.now()
            else:
                # Add new publication
                pub = Publication(
                    bibcode=paper_obj.bibcode,
                    title=paper_obj.title,
                    pubdate=getattr(paper_obj, "pubdate", None),
                    citation_count=cite_count,
                    author_id=author.id,
                    last_updated=datetime.datetime.now(),
                )
                session.add(pub)
            
            updated_sqlalchemy_pubs.append(pub)
        
        # session.commit() is handled by session_scope in the calling function
        return updated_sqlalchemy_pubs

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

                # Refresh author's publications first. This includes removal logic.
                # The database will be updated by fetch_author_publications.
                self.fetch_author_publications(author.id, max_rows)

                # Get the updated publications list from the current session
                # This list reflects changes made by fetch_author_publications
                publications = (
                    session.query(Publication).filter_by(author_id=author.id).all()
                )

                # Check citations for each publication
                for pub in publications:
                    citation_data = self.ads_wrapper.citations(
                        pub.bibcode,
                        fl="title,bibcode,author,date,doi,citation_count", # 'date' for pubdate of citing paper
                        rows=max_rows, # Use max_rows for citations as well
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

            # session.commit() handled by session_scope

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
        
        # Get all bibcodes of citing papers from the ADS response
        # Ensure papers_dict and 'bibcode' key exist
        citing_bibcodes_from_ads = []
        if hasattr(citation_data, 'papers_dict') and citation_data.papers_dict and 'bibcode' in citation_data.papers_dict:
             citing_bibcodes_from_ads = citation_data.papers_dict.get("bibcode", [])
        
        # Iterate through ADSPaper objects for detailed processing
        for paper in citation_data.papers: # ADSPaper objects
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

                # ADS paper.author is already a list of strings or a single string.
                # Ensure local citation.authors is comparable or consistently stored.
                # Storing as string is fine.
                ads_authors_str = str(getattr(paper, "author", []))
                if citation.authors != ads_authors_str:
                    citation.authors = ads_authors_str
                    updated = True
                
                # 'date' field from ADS for citing paper's publication date
                ads_pub_date = getattr(paper, "date", None) 
                if citation.publication_date != ads_pub_date:
                    citation.publication_date = ads_pub_date
                    updated = True

                ads_doi_val = getattr(paper, "doi", None)
                if isinstance(ads_doi_val, list): # Handle if DOI is a list
                    ads_doi_str = ";".join(ads_doi_val)
                else:
                    ads_doi_str = ads_doi_val

                if citation.doi != ads_doi_str:
                    citation.doi = ads_doi_str
                    updated = True

                if updated:
                    updated_citations.append(citation)
            else:
                # Create new citation
                doi_value = getattr(paper, "doi", None)
                if isinstance(doi_value, list):
                    doi_value = ";".join(doi_value)

                citation = Citation(
                    bibcode=paper.bibcode,
                    title=paper.title,
                    authors=str(getattr(paper, "author", [])),
                    publication_date=getattr(paper, "date", None), # 'date' from ADS
                    doi=doi_value,
                    publication_id=publication.id,
                    discovery_date=datetime.datetime.now(),
                )
                session.add(citation)
                new_citations.append(citation)

        # Update the publication's citation count based on the number of citing papers found
        # Use num_found for total, or len of the list of bibcodes if that's more representative of what's processed
        publication.citation_count = citation_data.num_found 
        publication.last_updated = datetime.datetime.now()

        # session.commit() handled by session_scope
        return CitationUpdate(
            new_citations=new_citations, updated_citations=updated_citations
        )

    def _display_citation_results(
        self,
        session, # Keep session if needed for querying author name, though it's passed in results now
        results: Dict[int, Dict[str, CitationUpdate]],
        verbose: bool = False,
    ) -> None:
        """
        Display the results of citation checks.

        Parameters
        ----------
        session : Session
            SQLAlchemy session, used to query author names.
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
                logger.warning(f"Author with ID {author_id} not found for displaying results.")
                continue

            author_name = f"{author.forename} {author.surname}"

            for bibcode, citation_update in author_results.items():
                publication = (
                    session.query(Publication)
                    .filter_by(bibcode=bibcode, author_id=author_id)
                    .first()
                )

                if not publication:
                    logger.warning(f"Publication with bibcode {bibcode} for author ID {author_id} not found.")
                    continue
                
                pub_title_display = publication.title
                if len(pub_title_display) > 70:
                     pub_title_display = pub_title_display[:67] + "..."


                # Display new citations
                if citation_update.new_citations:
                    self._print_citation_table(
                        author_name,
                        pub_title_display,
                        citation_update.new_citations,
                        "New",
                    )

                # Display updated citations if verbose
                if verbose and citation_update.updated_citations:
                    self._print_citation_table(
                        author_name,
                        pub_title_display,
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
        self.console.print(f"[yellow]Original Paper Title:[/yellow] {publication_title}")

        table = Table(box=box.ROUNDED, title=f"{citation_type} Citing Papers")
        table.add_column("Citing Paper Title", style="cyan", no_wrap=False, max_width=60)
        table.add_column("Citing Authors", style="green", no_wrap=False, max_width=40)
        table.add_column("Citing Date", style="yellow")
        table.add_column("ADS Link", style="blue", no_wrap=True)

        for citation in citations:
            # Truncate title if too long
            title = citation.title
            if len(title) > 55: # Adjusted for max_width
                title = title[:52] + "..."

            # Format authors
            authors_str = citation.authors
            if authors_str:
                # Try to get first author + et al. if it's a list-like string
                if authors_str.startswith('[') and 'et al.' not in authors_str:
                    try:
                        # Attempt to parse if it looks like a list of authors
                        authors_list = eval(authors_str) # Be cautious with eval
                        if isinstance(authors_list, list) and len(authors_list) > 1:
                            authors_str = f"{authors_list[0]}, et al."
                        elif isinstance(authors_list, list) and len(authors_list) == 1:
                            authors_str = authors_list[0]
                    except: # Fallback if eval fails or not a list
                        pass # Keep original authors_str
                
                if len(authors_str) > 35: # Adjusted for max_width
                     authors_str = authors_str[:32] + "..."
            else:
                authors_str = "-"


            # Create ADS link
            ads_link = f"https://ui.adsabs.harvard.edu/abs/{citation.bibcode}/abstract"

            # Format date
            date = citation.publication_date
            if date and len(date) > 10: # Assuming YYYY-MM-DD or YYYY-MM
                date = date[:10]

            table.add_row(title, authors_str, date or "-", ads_link)

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
        table.add_column("Title", style="cyan", no_wrap=False, max_width=60)
        table.add_column(
            "Citations\n(last 90 days)\n[per year]", justify="right", style="green"  # Corrected: removed '\' before '['
        )
        table.add_column("Pub Date", style="yellow") # Renamed column for clarity
        table.add_column("ADS Link", style="blue", no_wrap=True)

        total_citations = 0
        total_publications = len(publications)

        for pub in publications:
            # Get recent citations (last 90 days based on citing paper's publication_date)
            ninety_days_ago_str = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
            
            recent_citations = 0
            # Query citations linked to this publication
            citing_papers = session.query(Citation).filter_by(publication_id=pub.id).all()
            for citing_paper in citing_papers:
                try:
                    # Check if citing_paper.publication_date is not None and is a valid date string
                    if citing_paper.publication_date:
                        # ADS 'date' field can be YYYY-MM, YYYY-MM-DD, or YYYY-MM-DDTHH:MM:SSZ
                        # Get the date part by splitting at 'T'
                        date_only_str = citing_paper.publication_date.split('T')[0]
                        
                        citing_paper_date_parts = date_only_str.split('-')
                        citing_year = int(citing_paper_date_parts[0])
                        
                        # Default month to 1 if not present or 0
                        citing_month = 1
                        if len(citing_paper_date_parts) > 1:
                            month_val = int(citing_paper_date_parts[1])
                            citing_month = month_val if month_val != 0 else 1
                        
                        # Default day to 1 if not present or 0
                        citing_day = 1
                        if len(citing_paper_date_parts) > 2:
                            day_val = int(citing_paper_date_parts[2])
                            citing_day = day_val if day_val != 0 else 1
                        
                        citing_date_obj = datetime.datetime(citing_year, citing_month, citing_day)
                        ninety_days_ago_obj = datetime.datetime.strptime(ninety_days_ago_str, '%Y-%m-%d')

                        if citing_date_obj >= ninety_days_ago_obj:
                            recent_citations +=1
                except (ValueError, IndexError, TypeError) as e:
                    logger.debug(f"Could not parse date '{citing_paper.publication_date}' for recent citation check: {e}")
                    pass # Skip if date is invalid or not present


            # Create ADS link
            ads_link = f"https://ui.adsabs.harvard.edu/abs/{pub.bibcode}/abstract"

            # Calculate years since publication (of the original paper)
            years_since_pub = None # Default to None
            if pub.pubdate:
                try:
                    # Remove time part if present (though less common for pub.pubdate)
                    date_part = pub.pubdate.split('T')[0] 
                    pub_date_parts = date_part.split("-")
                    
                    year = int(pub_date_parts[0])
                    
                    month = 1 # Default month to January
                    if len(pub_date_parts) > 1:
                        month_val = int(pub_date_parts[1])
                        month = month_val if month_val != 0 else 1 # Default 00 to 1
                    
                    day = 1 # Default day to 1st
                    if len(pub_date_parts) > 2:
                        day_val = int(pub_date_parts[2])
                        day = day_val if day_val != 0 else 1 # Default 00 to 1
                    
                    pub_datetime_obj = datetime.datetime(year, month, day)
                    # Ensure years_since_pub is at least a small fraction for very recent papers
                    years_since_pub = max((datetime.datetime.now() - pub_datetime_obj).days / 365.25, 1/12.0) 
                except (ValueError, IndexError, TypeError) as e:
                    logger.debug(f"Could not parse pubdate '{pub.pubdate}' for years_since_pub calculation: {e}")
                    years_since_pub = None # Indicate it couldn't be calculated
            
            citations_per_year_str = "-"
            if years_since_pub is not None and pub.citation_count is not None:
                if years_since_pub > 0 : # Avoid division by zero
                    citations_per_year = pub.citation_count / years_since_pub
                    citations_per_year_str = f"{citations_per_year:.1f}"
                elif pub.citation_count > 0: # Many citations in less than a month (or if years_since_pub is near 0)
                     # Estimate for papers less than a month old but with citations
                     if years_since_pub < (1/12.0) and years_since_pub > 0:
                         citations_per_year_str = f"{pub.citation_count / years_since_pub:.1f}*" # Extrapolated
                     else: # If years_since_pub is exactly 0 (should be caught by max) or negative (error)
                         citations_per_year_str = "N/A"
                else: # No citations or years_since_pub is 0 and no citations
                    citations_per_year_str = "0.0"


            # Format title
            title_display = pub.title
            if len(title_display) > 55: 
                title_display = title_display[:52] + "..."

            table.add_row(
                title_display,
                f"{pub.citation_count or 0} ({recent_citations}) [{citations_per_year_str}]",
                pub.pubdate or "-",
                ads_link,
            )

            if pub.citation_count: 
                total_citations += pub.citation_count

        self.console.print(table)

        # Summary statistics
        self.console.print(f"\n[bold]Summary Statistics:[/bold]")
        self.console.print(f"Total Publications: [green]{total_publications}[/green]")
        self.console.print(f"Total Citations: [green]{total_citations}[/green]")

        if total_publications > 0:
            avg_citations = total_citations / total_publications if total_citations > 0 else 0.0
            self.console.print(
                f"Average Citations per Publication: [green]{avg_citations:.2f}[/green]"
            )

            # H-index calculation
            citation_counts = sorted(
                [p.citation_count or 0 for p in publications], reverse=True 
            )
            h_index = 0
            for i, count_val in enumerate(citation_counts):
                if count_val >= (i + 1):
                    h_index = i + 1
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
    subparsers = parser.add_subparsers(dest="command", help="Command to run", required=True)

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
        "--max-rows", type=int, default=2000, help="Maximum rows to return per query for publications and citations"
    )
    check_parser.add_argument(
        "--verbose", action="store_true", help="Show detailed output for updated citations"
    )

    # Generate report command
    report_parser = subparsers.add_parser("report", help="Generate citation report")
    report_parser.add_argument(
        "--author-id", type=int, help="Author ID to report on (default: all authors)"
    )

    # Parse arguments
    args = parser.parse_args()

    # Create tracker
    # Configure logging for the application if desired
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO").upper())
        
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
    # No 'else' needed due to 'required=True' in subparsers


if __name__ == "__main__":
    main()
