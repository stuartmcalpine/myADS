"""One-off search functionality for the citation tracker."""

import datetime
import logging
from typing import List, Optional
from myads import ADSPaper, ADSQuery
from rich.table import Table
from rich import box

logger = logging.getLogger(__name__)


class SearchManager:
    """Manages one-off author searches."""

    def __init__(self, console, ads_wrapper_getter):
        """
        Initialize the search manager.

        Parameters
        ----------
        console : Console
            Rich console for output.
        ads_wrapper_getter : callable
            Function that returns an ADSQueryWrapper instance.
        """
        self.console = console
        self.get_ads_wrapper = ads_wrapper_getter

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
    ) -> Optional[ADSQuery]:
        """
        Search for an author's publications directly from ADS without using the database.

        Parameters
        ----------
        surname : str
            Author's last name.
        forename : str
            Author's first name.
        orcid : str, optional
            Author's ORCID identifier.
        max_rows : int, optional
            Maximum number of results to return.
        sort : str, optional
            Sort order for results.
        output_format : str, optional
            Output format: 'table', 'json', or 'csv'.
        include_stats : bool, optional
            Whether to calculate and display summary statistics.
        first_author_only : bool, optional
            If True, search only for first author papers. Default False (any author position).

        Returns
        -------
        ADSQuery or None
            Query results if successful, None otherwise.
        """
        # Build query string
        author_field = "first_author" if first_author_only else "author"
        
        if orcid:
            q = (
                f"orcid_pub:{orcid} OR orcid_user:{orcid} OR "
                f'orcid_other:{orcid} OR {author_field}:"{surname}, {forename}"'
            )
        else:
            q = f'{author_field}:"{surname}, {forename}"'

        fl = "title,bibcode,author,citation_count,pubdate"

        search_type = "first author" if first_author_only else "any author position"
        self.console.print(
            f"[cyan]Searching ADS for {forename} {surname} ({search_type})...[/cyan]"
        )

        # Query ADS
        try:
            ads_wrapper = self.get_ads_wrapper()
            results = ads_wrapper.get(
                q=q, fl=fl, rows=max_rows, sort=sort, verbose=False
            )
        except Exception as e:
            self.console.print(f"[red]Error querying ADS: {e}[/red]")
            return None

        if not results or results.num_found == 0:
            self.console.print(
                f"[yellow]No publications found for {forename} {surname}.[/yellow]"
            )
            return None

        self.console.print(f"[green]Found {results.num_found} publication(s).[/green]\n")

        # Convert to list of papers
        papers = list(results.papers)

        if output_format == "table":
            self._display_search_results_table(
                surname, forename, papers, include_stats
            )
        elif output_format == "json":
            self._export_search_results_json(papers)
        elif output_format == "csv":
            self._export_search_results_csv(papers)
        else:
            self.console.print(f"[red]Unknown output format: {output_format}[/red]")

        return results

    def _display_search_results_table(
        self,
        surname: str,
        forename: str,
        papers: List[ADSPaper],
        include_stats: bool = True,
    ) -> None:
        """
        Display search results in a table format.
        """
        self.console.print(
            f"[bold]Publications for [cyan]{forename} {surname}[/cyan][/bold]\n"
        )

        table = Table(
            title="Search Results",
            box=box.ROUNDED,
            row_styles=["dim", ""],
        )
        table.add_column("Title", style="cyan", no_wrap=False, max_width=60)
        table.add_column("Citations\n[per year]", justify="right", style="green")
        table.add_column("Pub Date", style="yellow")
        table.add_column("ADS Link", style="blue", no_wrap=True)

        total_citations = 0

        for paper in papers:
            cite_count = getattr(paper, "citation_count", 0) or 0
            pubdate = getattr(paper, "pubdate", "")

            # Calculate years since publication and citations per year
            years_since_pub = None
            citations_per_year_str = "-"

            if pubdate:
                try:
                    date_part = pubdate.split("T")[0]
                    pub_date_parts = date_part.split("-")

                    year = int(pub_date_parts[0])
                    month = 1
                    if len(pub_date_parts) > 1:
                        month_val = int(pub_date_parts[1])
                        month = month_val if month_val != 0 else 1

                    day = 1
                    if len(pub_date_parts) > 2:
                        day_val = int(pub_date_parts[2])
                        day = day_val if day_val != 0 else 1

                    pub_datetime_obj = datetime.datetime(year, month, day)
                    years_since_pub = max(
                        (datetime.datetime.now() - pub_datetime_obj).days / 365.25,
                        1 / 12.0,
                    )

                    if years_since_pub > 0 and cite_count is not None:
                        citations_per_year = cite_count / years_since_pub
                        citations_per_year_str = f"{citations_per_year:.1f}"
                except (ValueError, IndexError, TypeError):
                    pass

            # Format title
            title_display = paper.title
            if len(title_display) > 55:
                title_display = title_display[:52] + "..."

            # Create ADS link
            ads_link = f"https://ui.adsabs.harvard.edu/abs/{paper.bibcode}/abstract"

            table.add_row(
                title_display,
                f"{cite_count} [{citations_per_year_str}]",
                pubdate or "-",
                ads_link,
            )

            total_citations += cite_count

        self.console.print(table)

        # Display statistics if requested
        if include_stats:
            self.console.print(f"\n[bold]Summary Statistics:[/bold]")
            self.console.print(f"Total Publications: [green]{len(papers)}[/green]")
            self.console.print(f"Total Citations: [green]{total_citations}[/green]")

            if len(papers) > 0:
                avg_citations = (
                    total_citations / len(papers) if total_citations > 0 else 0.0
                )
                self.console.print(
                    f"Average Citations per Publication: [green]{avg_citations:.2f}[/green]"
                )

                # H-index calculation
                citation_counts = sorted(
                    [getattr(p, "citation_count", 0) or 0 for p in papers],
                    reverse=True,
                )
                h_index = 0
                for i, count_val in enumerate(citation_counts):
                    if count_val >= (i + 1):
                        h_index = i + 1
                    else:
                        break

                self.console.print(f"H-index: [green]{h_index}[/green]")

    def _export_search_results_json(self, papers: List[ADSPaper]) -> None:
        """
        Export search results as JSON.
        """
        import json

        results = []
        for paper in papers:
            paper_dict = {
                "title": paper.title,
                "bibcode": paper.bibcode,
                "authors": getattr(paper, "author", []),
                "citation_count": getattr(paper, "citation_count", 0) or 0,
                "pubdate": getattr(paper, "pubdate", ""),
            }
            results.append(paper_dict)

        print(json.dumps(results, indent=2))

    def _export_search_results_csv(self, papers: List[ADSPaper]) -> None:
        """
        Export search results as CSV.
        """
        import csv
        import sys

        writer = csv.writer(sys.stdout)
        writer.writerow(["Title", "Bibcode", "Authors", "Citations", "PubDate"])

        for paper in papers:
            authors = getattr(paper, "author", [])
            if isinstance(authors, list):
                authors = "; ".join(authors)

            writer.writerow(
                [
                    paper.title,
                    paper.bibcode,
                    authors,
                    getattr(paper, "citation_count", 0) or 0,
                    getattr(paper, "pubdate", ""),
                ]
            )
