"""Citation checking and processing."""

import datetime
import logging
from typing import Dict, List
from dataclasses import dataclass
from sqlalchemy.orm import Session
from rich.table import Table
from rich import box

from .models import Author, Publication, Citation

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

    def _process_citations(
        self, session: Session, publication: Publication, citation_data
    ) -> CitationUpdate:
        """
        Process citations for a publication.
        """
        new_citations = []
        updated_citations = []

        for paper in citation_data.papers:
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

                ads_authors_str = str(getattr(paper, "author", []))
                if citation.authors != ads_authors_str:
                    citation.authors = ads_authors_str
                    updated = True

                ads_pub_date = getattr(paper, "date", None)
                if citation.publication_date != ads_pub_date:
                    citation.publication_date = ads_pub_date
                    updated = True

                ads_doi_val = getattr(paper, "doi", None)
                if isinstance(ads_doi_val, list):
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
                    publication_date=getattr(paper, "date", None),
                    doi=doi_value,
                    publication_id=publication.id,
                    discovery_date=datetime.datetime.now(),
                )
                session.add(citation)
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
            # Truncate title if too long
            title = citation.title
            if len(title) > 55:
                title = title[:52] + "..."

            # Format authors
            authors_str = citation.authors
            if authors_str:
                if authors_str.startswith("[") and "et al." not in authors_str:
                    try:
                        authors_list = eval(authors_str)
                        if isinstance(authors_list, list) and len(authors_list) > 1:
                            authors_str = f"{authors_list[0]}, et al."
                        elif isinstance(authors_list, list) and len(authors_list) == 1:
                            authors_str = authors_list[0]
                    except:
                        pass

                if len(authors_str) > 35:
                    authors_str = authors_str[:32] + "..."
            else:
                authors_str = "-"

            # Create ADS link
            ads_link = (
                f"https://ui.adsabs.harvard.edu/abs/{citation.bibcode}/abstract"
            )

            # Format date
            date = citation.publication_date
            if date and len(date) > 10:
                date = date[:10]

            table.add_row(title, authors_str, date or "-", ads_link)

        self.console.print(table)
