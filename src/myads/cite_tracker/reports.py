"""Report generation for the citation tracker."""

import collections
import datetime
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich import box

from .models import Author, Publication
from .utils import ads_link, h_index, ordinal, parse_ads_date, truncate, years_since

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates citation reports."""

    def __init__(self, console):
        """
        Initialize the report generator.

        Parameters
        ----------
        console : Console
            Rich console for output.
        """
        self.console = console

    def generate_author_report(
        self, session: Session, author: Author, publications: List[Publication], extended: bool = False
    ) -> None:
        """
        Generate a citation report for a specific author.

        Parameters
        ----------
        session : Session
            SQLAlchemy session.
        author : Author
            Author to generate report for.
        publications : List[Publication]
            List of publications to include in the report.
        extended : bool, optional
            Show per-paper details with a quarterly citation chart.
        """
        if not publications:
            self.console.print(
                f"[yellow]No publications found for {author.forename} {author.surname}.[/yellow]"
            )
            return

        if extended:
            self._format_extended_report(author, publications)
        else:
            self._format_publication_table(author, publications)

    def _format_extended_report(
        self, author: Author, publications: List[Publication]
    ) -> None:
        """Render the extended per-paper view with quarterly citation charts."""
        self.console.print(
            f"\n[bold]Extended Citation Report — [cyan]{author.forename} {author.surname}[/cyan][/bold]"
        )

        for i, pub in enumerate(publications):
            self.console.print()
            self.console.print(Rule(style="dim"))
            self._format_extended_paper(author, pub, i + 1, len(publications))

        self.console.print()
        self.console.print(Rule(style="dim"))

        self._print_summary(publications)

    def _format_extended_paper(
        self,
        author: Author,
        pub: Publication,
        pub_num: int,
        total_pubs: int,
    ) -> None:
        """Render details and quarterly citation chart for a single publication."""
        pub_date = parse_ads_date(pub.pubdate)
        year_display = str(pub_date.year) if pub_date else "-"

        per_year_str = "-"
        if pub_date and pub.citation_count:
            per_year_str = f"{pub.citation_count / years_since(pub_date):.1f}"

        citation_dates = [parse_ads_date(c.publication_date) for c in pub.citations]
        position = self._find_author_position(
            pub.authors, author.surname, author.forename
        )

        self.console.print(
            f"[bold cyan]Paper {pub_num} of {total_pubs}[/bold cyan]  [dim]ID: {pub.id}[/dim]"
        )
        self.console.print(f"[bold]{pub.title}[/bold]")
        self.console.print(f"[blue]{ads_link(pub.bibcode)}[/blue]")
        self.console.print(
            f"[yellow]{year_display}[/yellow]  ·  "
            f"Position: [green]{position}[/green]  ·  "
            f"Citations: [green]{pub.citation_count or 0}[/green]  ·  "
            f"Last 90d: [green]{self._count_recent(citation_dates)}[/green]  ·  "
            f"Per year: [green]{per_year_str}[/green]"
        )
        self.console.print("\n[bold]Citations per quarter:[/bold]")
        self._render_quarter_chart(pub_date, citation_dates)

    @staticmethod
    def _count_recent(
        citation_dates: List[Optional[datetime.datetime]], days: int = 90
    ) -> int:
        """Count citations dated within the last ``days`` days."""
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        return sum(1 for d in citation_dates if d and d >= cutoff)

    def _render_quarter_chart(
        self,
        pub_date: Optional[datetime.datetime],
        citation_dates: List[Optional[datetime.datetime]],
    ) -> None:
        """Render a horizontal Unicode bar chart of citations per quarter."""
        if not citation_dates:
            self.console.print("[dim]  No citations recorded yet.[/dim]")
            return

        def quarter_of(d: datetime.datetime) -> Tuple[int, int]:
            return (d.year, (d.month - 1) // 3 + 1)

        # Bin by (year, quarter)
        quarter_counts = collections.Counter(
            quarter_of(d) for d in citation_dates if d
        )

        if not quarter_counts:
            self.console.print("[dim]  No dated citations found.[/dim]")
            return

        # Determine range
        start_q = quarter_of(pub_date) if pub_date else min(quarter_counts)
        end_q = quarter_of(datetime.datetime.now())

        # Walk every quarter from start to end
        quarters = []
        y, q = start_q
        while (y, q) <= end_q:
            quarters.append((y, q))
            q += 1
            if q > 4:
                q, y = 1, y + 1

        max_count = max(quarter_counts.values())
        bar_width = 30

        for year, quarter in reversed(quarters):
            count = quarter_counts.get((year, quarter), 0)
            bar_len = int(round(count / max_count * bar_width))
            line = Text()
            line.append(f"  {f'{year} Q{quarter}':<8}", style="dim")
            line.append("  ")
            line.append("█" * bar_len, style="green")
            line.append(f"  {count}")
            self.console.print(line)

    def _find_author_position(
        self, author_list_str: Optional[str], surname: str, forename: str
    ) -> str:
        """
        Find the position of the author in the author list.

        An entry matches if its surname equals ``surname`` (case-insensitive)
        and, when both are available, the forename initials agree.

        Parameters
        ----------
        author_list_str : str or None
            Semicolon-separated string of authors ("Surname, Forename").
        surname : str
            Author's surname.
        forename : str
            Author's forename.

        Returns
        -------
        str
            Position string like "1st", "2nd", "23rd", or "?" if not found.
        """
        if not author_list_str:
            return "?"

        target_surname = surname.strip().lower()
        target_initial = forename.strip()[:1].lower()

        for i, entry in enumerate(author_list_str.split(";")):
            entry_surname, _, entry_forename = entry.partition(",")
            if entry_surname.strip().lower() != target_surname:
                continue
            entry_initial = entry_forename.strip()[:1].lower()
            if target_initial and entry_initial and entry_initial != target_initial:
                continue
            return ordinal(i + 1)

        return "?"

    def _format_publication_table(
        self, author: Author, publications: List[Publication]
    ) -> None:
        """
        Format and display a publication table.
        """
        self.console.print(
            f"\n[bold]Citation Report for [cyan]{author.forename} {author.surname}[/cyan][/bold]"
        )

        table = Table(
            title="Publications by Citation Count",
            box=box.ROUNDED,
            row_styles=["dim", ""],
        )
        table.add_column("ID", justify="right", style="magenta", width=4)
        table.add_column("Pos", justify="center", style="blue", width=4)
        table.add_column("Title", style="cyan", no_wrap=False, max_width=60)
        table.add_column(
            "Citations\n(90d)\n(per yr)", justify="right", style="green", width=18
        )
        table.add_column("Year", style="yellow", width=6)
        table.add_column("ADS Link", style="blue", no_wrap=True)

        for pub in publications:
            recent_citations = self._count_recent(
                [parse_ads_date(c.publication_date) for c in pub.citations]
            )

            pub_date = parse_ads_date(pub.pubdate)
            year_display = str(pub_date.year) if pub_date else "-"
            citations_per_year_str = "-"
            if pub_date and pub.citation_count is not None:
                citations_per_year_str = (
                    f"{pub.citation_count / years_since(pub_date):.1f}"
                )

            author_position = self._find_author_position(
                pub.authors, author.surname, author.forename
            )

            cite_info = f"{pub.citation_count or 0} ({recent_citations}) ({citations_per_year_str})"

            table.add_row(
                str(pub.id),
                author_position,
                truncate(pub.title, 38),
                cite_info,
                year_display,
                ads_link(pub.bibcode),
            )

        self.console.print(table)
        self._print_summary(publications)

    def _print_summary(self, publications: List[Publication]) -> None:
        """Print total/average citations and h-index for a set of publications."""
        total_publications = len(publications)
        total_citations = sum(p.citation_count or 0 for p in publications)

        self.console.print("\n[bold]Summary Statistics:[/bold]")
        self.console.print(f"Total Publications: [green]{total_publications}[/green]")
        self.console.print(f"Total Citations: [green]{total_citations}[/green]")

        if total_publications > 0:
            avg_citations = total_citations / total_publications
            self.console.print(
                f"Average Citations per Publication: [green]{avg_citations:.2f}[/green]"
            )
            h = h_index(p.citation_count for p in publications)
            self.console.print(f"H-index: [green]{h}[/green]")
