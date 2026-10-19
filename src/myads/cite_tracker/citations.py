"""Citation checking and processing."""

import ast
import datetime
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from rich.table import Table
from rich import box

from .models import Author, Publication, Citation
from .utils import ads_link, truncate

logger = logging.getLogger(__name__)


@dataclass
class CitationUpdate:
    """Data class to hold citation update information."""

    new_citations: List[Citation]
    updated_citations: List[Citation]


class CitationManager:
    """Manages citation checking and processing."""

    def __init__(self, console, ads_wrapper_getter):
        """
        Initialize the citation manager.

        Parameters
        ----------
        console : Console
            Rich console for output.
        ads_wrapper_getter : callable
            Function that returns an ADSQueryWrapper instance.
        """
        self.console = console
        self.get_ads_wrapper = ads_wrapper_getter

    def check_citations(
        self,
        session: Session,
        publications: List[Publication],
        max_rows: int = 2000,
    ) -> Dict[str, CitationUpdate]:
        """
        Check for new citations to tracked publications.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        publications : List[Publication]
            List of publications to check.
        max_rows : int, optional
            Maximum number of citations to fetch per publication.

        Returns
        -------
        Dict[str, CitationUpdate]
            Dictionary of citation updates by bibcode.
        """
        results = {}
        ads_wrapper = self.get_ads_wrapper()

        # Check citations for each publication
        for pub in publications:
            citation_data = ads_wrapper.citations(
                pub.bibcode,
                fl="title,bibcode,author,date,doi,citation_count",
                rows=max_rows,
            )

            if citation_data and citation_data.num_found > 0:
                citation_update = self._process_citations(session, pub, citation_data)
                if (
                    citation_update.new_citations
                    or citation_update.updated_citations
                ):
                    results[pub.bibcode] = citation_update

        return results

    @staticmethod
    def _citation_fields(paper) -> Dict[str, Optional[str]]:
        """Extract the Citation column values from an ADS paper."""
        doi = getattr(paper, "doi", None)
        if isinstance(doi, list):
            doi = ";".join(doi)
        return {
            "title": getattr(paper, "title", None) or "",
            "authors": str(getattr(paper, "author", None) or []),
            "publication_date": getattr(paper, "date", None),
            "doi": doi,
        }

    def _process_citations(
        self, session: Session, publication: Publication, citation_data
    ) -> CitationUpdate:
        """
        Process citations for a publication.
        """
        new_citations = []
        updated_citations = []

        existing = {c.bibcode: c for c in publication.citations}

        for paper in citation_data.papers:
            fields = self._citation_fields(paper)
            citation = existing.get(paper.bibcode)

            if citation:
                # Update any fields that have changed in ADS
                updated = False
                for name, value in fields.items():
                    if getattr(citation, name) != value:
                        setattr(citation, name, value)
                        updated = True

                if updated:
                    updated_citations.append(citation)
            else:
                citation = Citation(
                    bibcode=paper.bibcode,
                    discovery_date=datetime.datetime.now(),
                    **fields,
                )
                publication.citations.append(citation)
                existing[paper.bibcode] = citation
                new_citations.append(citation)

        # Update the publication's citation count
        publication.citation_count = citation_data.num_found
        publication.last_updated = datetime.datetime.now()

        return CitationUpdate(
            new_citations=new_citations, updated_citations=updated_citations
        )

    def display_citation_results(
        self,
        session: Session,
        author: Author,
        results: Dict[str, CitationUpdate],
        verbose: bool = False,
    ) -> None:
        """
        Display the results of citation checks for an author.
        """
        if not results:
            return

        author_name = f"{author.forename} {author.surname}"

        for bibcode, citation_update in results.items():
            publication = (
                session.query(Publication)
                .filter_by(bibcode=bibcode, author_id=author.id)
                .first()
            )

            if not publication:
                logger.warning(
                    f"Publication with bibcode {bibcode} for author ID {author.id} not found."
                )
                continue

            pub_title_display = truncate(publication.title, 70)

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
        """
        title_color = "green" if citation_type == "New" else "blue"

        self.console.print(
            f"\n[bold {title_color}]{citation_type} citations for paper by {author_name}:[/bold {title_color}]"
        )
        self.console.print(
            f"[yellow]Original Paper Title:[/yellow] {publication_title}"
        )

        table = Table(box=box.ROUNDED, title=f"{citation_type} Citing Papers")
        table.add_column(
            "Citing Paper Title", style="cyan", no_wrap=False, max_width=60
        )
        table.add_column(
            "Citing Authors", style="green", no_wrap=False, max_width=40
        )
        table.add_column("Citing Date", style="yellow")
        table.add_column("ADS Link", style="blue", no_wrap=True)

        for citation in citations:
            # Authors are stored as the repr of the ADS author list
            authors_str = citation.authors
            if authors_str and authors_str.startswith("["):
                try:
                    authors_list = ast.literal_eval(authors_str)
                except (ValueError, SyntaxError):
                    authors_list = None
                if isinstance(authors_list, list):
                    if len(authors_list) > 1:
                        authors_str = f"{authors_list[0]}, et al."
                    elif authors_list:
                        authors_str = authors_list[0]
                    else:
                        authors_str = ""

            date = (citation.publication_date or "")[:10]

            table.add_row(
                truncate(citation.title, 55),
                truncate(authors_str, 35) or "-",
                date or "-",
                ads_link(citation.bibcode),
            )

        self.console.print(table)
