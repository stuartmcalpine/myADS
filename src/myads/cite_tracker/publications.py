"""Publication management for the citation tracker."""

import datetime
import logging
from typing import List, Optional, Set
from sqlalchemy.orm import Session
from rich.prompt import Confirm
from rich.table import Table
from rich import box

from myads import ADSQueryWrapper, ADSPaper
from .models import Author, Publication, RejectedPaper

logger = logging.getLogger(__name__)


class PublicationManager:
    """Manages publication operations."""

    def __init__(self, console, ads_wrapper_getter):
        """
        Initialize the publication manager.

        Parameters
        ----------
        console : Console
            Rich console for output.
        ads_wrapper_getter : callable
            Function that returns an ADSQueryWrapper instance.
        """
        self.console = console
        self.get_ads_wrapper = ads_wrapper_getter

    def ignore_publication(
        self, session: Session, publication_id: int, reason: Optional[str] = None
    ) -> bool:
        """
        Mark a publication as ignored.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        publication_id : int
            ID of the publication to ignore.
        reason : str, optional
            Reason for ignoring the publication.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        pub = session.query(Publication).filter_by(id=publication_id).first()

        if not pub:
            self.console.print(
                f"[yellow]No publication found with ID {publication_id}.[/yellow]"
            )
            return False

        if pub.ignored:
            self.console.print(
                f"[yellow]Publication {publication_id} is already ignored.[/yellow]"
            )
            return False

        pub.ignored = True
        pub.ignore_reason = reason

        self.console.print(
            f"[green]Publication '{pub.title[:50]}...' marked as ignored.[/green]"
        )
        if reason:
            self.console.print(f"[dim]Reason: {reason}[/dim]")

        return True

    def unignore_publication(self, session: Session, publication_id: int) -> bool:
        """
        Unmark a publication as ignored.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        publication_id : int
            ID of the publication to unignore.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        pub = session.query(Publication).filter_by(id=publication_id).first()

        if not pub:
            self.console.print(
                f"[yellow]No publication found with ID {publication_id}.[/yellow]"
            )
            return False

        if not pub.ignored:
            self.console.print(
                f"[yellow]Publication {publication_id} is not ignored.[/yellow]"
            )
            return False

        pub.ignored = False
        pub.ignore_reason = None

        self.console.print(
            f"[green]Publication '{pub.title[:50]}...' is now being tracked.[/green]"
        )

        return True

    def list_ignored_publications(
        self, session: Session, author_id: Optional[int] = None
    ) -> None:
        """
        Display a table of ignored publications.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        author_id : int, optional
            ID of a specific author. If None, show all ignored publications.
        """
        query = session.query(Publication).filter_by(ignored=True)

        if author_id:
            query = query.filter_by(author_id=author_id)

        ignored_pubs = query.all()

        if not ignored_pubs:
            self.console.print("[yellow]No ignored publications found.[/yellow]")
            return

        table = Table(title="Ignored Publications", box=box.ROUNDED)
        table.add_column("ID", justify="right", style="cyan")
        table.add_column("Author", style="green")
        table.add_column("Title", style="yellow", no_wrap=False, max_width=50)
        table.add_column("Reason", style="magenta", no_wrap=False, max_width=30)

        for pub in ignored_pubs:
            author = session.query(Author).filter_by(id=pub.author_id).first()
            author_name = (
                f"{author.forename} {author.surname}" if author else "Unknown"
            )

            table.add_row(
                str(pub.id),
                author_name,
                pub.title,
                pub.ignore_reason or "-",
            )

        self.console.print(table)

    def clear_rejected_papers(
        self, session: Session, author_id: Optional[int] = None
    ) -> int:
        """
        Clear rejected papers from deep check memory.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        author_id : int, optional
            ID of a specific author. If None, clear all rejected papers.

        Returns
        -------
        int
            Number of rejected papers cleared.
        """
        query = session.query(RejectedPaper)

        if author_id:
            author = session.query(Author).filter_by(id=author_id).first()
            if not author:
                self.console.print(
                    f"[yellow]No author found with ID {author_id}.[/yellow]"
                )
                return 0
            query = query.filter_by(author_id=author_id)
            author_name = f"{author.forename} {author.surname}"

        count = query.count()
        
        if count == 0:
            if author_id:
                self.console.print(
                    f"[yellow]No rejected papers found for author ID {author_id}.[/yellow]"
                )
            else:
                self.console.print("[yellow]No rejected papers found.[/yellow]")
            return 0

        # Delete all matching rejected papers
        query.delete()

        if author_id:
            self.console.print(
                f"[green]Cleared {count} rejected paper(s) for {author_name}.[/green]"
            )
        else:
            self.console.print(
                f"[green]Cleared {count} rejected paper(s) for all authors.[/green]"
            )

        return count

    def list_rejected_papers(
        self, session: Session, author_id: Optional[int] = None
    ) -> None:
        """
        Display a table of rejected papers from deep check.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        author_id : int, optional
            ID of a specific author. If None, show all rejected papers.
        """
        query = session.query(RejectedPaper)

        if author_id:
            query = query.filter_by(author_id=author_id)

        rejected_papers = query.all()

        if not rejected_papers:
            self.console.print("[yellow]No rejected papers found.[/yellow]")
            return

        table = Table(title="Rejected Papers (Deep Check)", box=box.ROUNDED)
        table.add_column("ID", justify="right", style="cyan")
        table.add_column("Author", style="green")
        table.add_column("Bibcode", style="yellow")
        table.add_column("Rejected Date", style="magenta")

        for rejected in rejected_papers:
            author = session.query(Author).filter_by(id=rejected.author_id).first()
            author_name = (
                f"{author.forename} {author.surname}" if author else "Unknown"
            )

            rejected_date = (
                rejected.rejected_date.strftime("%Y-%m-%d")
                if rejected.rejected_date
                else "-"
            )

            table.add_row(
                str(rejected.id),
                author_name,
                rejected.bibcode,
                rejected_date,
            )

        self.console.print(table)

    def fetch_author_publications(
        self, session: Session, author_id: int, max_rows: int = 2000, deep: bool = False
    ) -> List[Publication]:
        """
        Fetch publications for an author from ADS, update local DB,
        and optionally remove local-only entries.
        """
        author = session.query(Author).filter_by(id=author_id).first()

        if not author:
            self.console.print(
                f"[yellow]No author found with ID {author_id} for fetching publications.[/yellow]"
            )
            raise ValueError(f"No author found with ID {author_id}")

        # Get locally stored publications (excluding ignored ones)
        local_pubs_before_fetch = (
            session.query(Publication)
            .filter_by(author_id=author.id, ignored=False)
            .all()
        )
        local_bibcodes_before_fetch = {p.bibcode for p in local_pubs_before_fetch}

        # Build the ADS query string - search first_author for regular tracking
        if author.orcid:
            q = (
                f"orcid_pub:{author.orcid} OR orcid_user:{author.orcid} OR "
                f'orcid_other:{author.orcid} OR first_author:"{author.surname}, {author.forename}"'
            )
        else:
            q = f'first_author:"{author.surname}, {author.forename}"'

        fl = "title,bibcode,author,citation_count,pubdate"

        # Query ADS
        ads_wrapper = self.get_ads_wrapper()
        ads_api_results = ads_wrapper.get(
            q=q, fl=fl, rows=max_rows, sort="pubdate desc", verbose=False
        )

        current_ads_papers_list = []
        ads_bibcodes_from_api = set()

        if ads_api_results and ads_api_results.papers:
            try:
                current_ads_papers_list = list(ads_api_results.papers)
                ads_bibcodes_from_api = {
                    p.bibcode
                    for p in current_ads_papers_list
                    if hasattr(p, "bibcode")
                }
            except TypeError:
                if ads_api_results.papers:
                    current_ads_papers_list = ads_api_results.papers
                    ads_bibcodes_from_api = {
                        p.bibcode
                        for p in current_ads_papers_list
                        if hasattr(p, "bibcode")
                    }

        if not ads_api_results or ads_api_results.num_found == 0:
            msg = f"[yellow]No publications found in ADS for {author.forename} {author.surname}."
            if author.orcid:
                msg += f"\nSearched: ORCID {author.orcid} OR first author by name."
                msg += "\nTry: Verify ORCID is correct, check name spelling, or use --deep to search all author positions."
            else:
                msg += f"\nSearched: First author papers by name only."
                msg += "\nTry: Add an ORCID for better results, check name spelling, or use --deep to search all author positions."
            msg += "[/yellow]"
            self.console.print(msg)

        # Identify local publications not found in current ADS results.
        # Exclude papers that were deliberately added via deep check — those
        # will never appear in the ORCID/first-author query by design.
        deep_added_bibcodes = {
            p.bibcode for p in local_pubs_before_fetch if p.added_via_deep
        }
        bibcodes_to_check_for_removal = (
            local_bibcodes_before_fetch - ads_bibcodes_from_api - deep_added_bibcodes
        )

        if bibcodes_to_check_for_removal:
            self.console.print(
                f"\n[bold yellow]Checking for local publications not found in current ADS results for {author.forename} {author.surname}:[/bold yellow]"
            )
            for bibcode_to_remove in bibcodes_to_check_for_removal:
                pub_to_remove = next(
                    (
                        p
                        for p in local_pubs_before_fetch
                        if p.bibcode == bibcode_to_remove
                    ),
                    None,
                )
                if pub_to_remove:
                    display_title = pub_to_remove.title
                    if len(display_title) > 70:
                        display_title = display_title[:67] + "..."

                    self.console.print(
                        f"Local entry: [cyan]{display_title}[/cyan] (Bibcode: {pub_to_remove.bibcode})"
                    )

                    if not self.console.is_interactive:
                        self.console.print(
                            "[yellow]Non-interactive mode. Skipping removal prompt. Entry will be kept.[/yellow]"
                        )
                        continue

                    # Explain why this might happen before asking
                    self.console.print(
                        "[dim]Common reasons: Author metadata corrected in ADS, ORCID updated, or paper retracted.[/dim]"
                    )

                    confirmation = Confirm.ask(
                        f"Paper not found in latest ADS results. Remove from local database?",
                        default=False,
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

        # Update local database with current ADS publications
        self._update_publications(session, author, current_ads_papers_list)

        # Deep check if requested
        if deep:
            self._deep_check_author(
                session, author, max_rows, ads_bibcodes_from_api
            )

        # Return the final list of publications for this author from the DB
        final_author_pubs_in_db = (
            session.query(Publication)
            .filter_by(author_id=author.id, ignored=False)
            .all()
        )
        return final_author_pubs_in_db

    def _deep_check_author(
        self,
        session: Session,
        author: Author,
        max_rows: int,
        known_bibcodes: Set[str],
    ) -> None:
        """
        Perform a deep check by searching with name in any author position and prompting for confirmation.
        """
        self.console.print(
            f"\n[bold cyan]Performing deep check for {author.forename} {author.surname}...[/bold cyan]"
        )

        # Query by any author position (not just first author)
        q = f'author:"{author.surname}, {author.forename}"'
        fl = "title,bibcode,author,citation_count,pubdate,abstract"

        ads_wrapper = self.get_ads_wrapper()
        name_only_results = ads_wrapper.get(
            q=q, fl=fl, rows=max_rows, sort="pubdate desc", verbose=False
        )

        if not name_only_results or name_only_results.num_found == 0:
            self.console.print(
                f"[yellow]No additional papers found in deep check.\n"
                f"Searched: author:\"{author.surname}, {author.forename}\" (any author position by name).\n"
                f"This means either all your papers are already tracked, or name spelling doesn't match ADS records.[/yellow]"
            )
            return

        # Get rejected bibcodes for this author
        rejected_bibcodes = {
            r.bibcode
            for r in session.query(RejectedPaper).filter_by(author_id=author.id).all()
        }

        # Get ignored bibcodes
        ignored_bibcodes = {
            p.bibcode
            for p in session.query(Publication)
            .filter_by(author_id=author.id, ignored=True)
            .all()
        }

        # Find new candidates
        all_name_bibcodes = {
            p.bibcode for p in name_only_results.papers if hasattr(p, "bibcode")
        }
        candidate_bibcodes = (
            all_name_bibcodes - known_bibcodes - rejected_bibcodes - ignored_bibcodes
        )

        if not candidate_bibcodes:
            self.console.print(
                "[green]No new candidate papers found in deep check.[/green]"
            )
            return

        self.console.print(
            f"[yellow]Found {len(candidate_bibcodes)} candidate paper(s) not in your tracked publications.[/yellow]\n"
        )

        # Get full paper objects for candidates
        candidate_papers = [
            p for p in name_only_results.papers if p.bibcode in candidate_bibcodes
        ]

        for paper in candidate_papers:
            # Display paper info
            self.console.print(f"[bold cyan]Title:[/bold cyan] {paper.title}")
            self.console.print(f"[bold cyan]Bibcode:[/bold cyan] {paper.bibcode}")

            # Show authors
            authors_list = getattr(paper, "author", [])
            if authors_list:
                if len(authors_list) > 5:
                    author_str = ", ".join(authors_list[:5]) + ", et al."
                else:
                    author_str = ", ".join(authors_list)
                self.console.print(f"[bold cyan]Authors:[/bold cyan] {author_str}")

            # Show year
            pubdate = getattr(paper, "pubdate", "")
            if pubdate:
                year = pubdate.split("-")[0]
                self.console.print(f"[bold cyan]Year:[/bold cyan] {year}")

            # Show abstract snippet
            abstract = getattr(paper, "abstract", "")
            if abstract:
                snippet = abstract[:200] + "..." if len(abstract) > 200 else abstract
                self.console.print(f"[bold cyan]Abstract:[/bold cyan] {snippet}")

            self.console.print("")

            if not self.console.is_interactive:
                self.console.print(
                    "[yellow]Non-interactive mode. Skipping confirmation. Paper will not be added.[/yellow]\n"
                )
                continue

            # Ask for confirmation
            confirmation = Confirm.ask(
                f"Add this paper to tracking for {author.forename} {author.surname}?",
                default=False,
            )

            if confirmation:
                # Add to publications and flag as deep-added so future normal
                # checks don't prompt to remove it (it won't appear in the
                # ORCID query since the ORCID isn't linked in ADS).
                self._update_publications(session, author, [paper])
                pub = (
                    session.query(Publication)
                    .filter_by(bibcode=paper.bibcode, author_id=author.id)
                    .first()
                )
                if pub:
                    pub.added_via_deep = True
                self.console.print(
                    f"[green]Added '{paper.title[:50]}...' to tracked publications.[/green]\n"
                )
            else:
                # Add to rejected papers
                rejected = RejectedPaper(
                    bibcode=paper.bibcode,
                    author_id=author.id,
                    rejected_date=datetime.datetime.now(),
                )
                session.add(rejected)
                self.console.print(
                    f"[red]Marked '{paper.title[:50]}...' as rejected.[/red]\n"
                )

    def _update_publications(
        self, session: Session, author: Author, current_ads_papers: List[ADSPaper]
    ) -> List[Publication]:
        """
        Update the publications for an author in the database based on a list of ADSPaper objects.
        """
        updated_sqlalchemy_pubs = []

        for paper_obj in current_ads_papers:
            # Check if publication exists (including ignored ones)
            pub = (
                session.query(Publication)
                .filter_by(bibcode=paper_obj.bibcode, author_id=author.id)
                .first()
            )

            try:
                cite_count = int(getattr(paper_obj, "citation_count", 0) or 0)
            except:
                cite_count = 0

            # Get author list and store as semicolon-separated string
            authors_list = getattr(paper_obj, "author", [])
            if isinstance(authors_list, list):
                authors_str = "; ".join(authors_list)
            else:
                authors_str = str(authors_list) if authors_list else ""

            if pub:
                # Update existing publication (but don't change ignored status)
                pub.title = paper_obj.title
                pub.citation_count = cite_count
                pub.pubdate = getattr(paper_obj, "pubdate", None)
                pub.authors = authors_str
                pub.last_updated = datetime.datetime.now()
            else:
                # Add new publication
                pub = Publication(
                    bibcode=paper_obj.bibcode,
                    title=paper_obj.title,
                    pubdate=getattr(paper_obj, "pubdate", None),
                    authors=authors_str,
                    citation_count=cite_count,
                    author_id=author.id,
                    last_updated=datetime.datetime.now(),
                    ignored=False,
                )
                session.add(pub)

            updated_sqlalchemy_pubs.append(pub)

        return updated_sqlalchemy_pubs
