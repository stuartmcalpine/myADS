"""Report generation for the citation tracker."""

import collections
import datetime
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich import box

from .models import Author, Publication, Citation

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
        """
        if not publications:
            self.console.print(
                f"[yellow]No publications found for {author.forename} {author.surname}.[/yellow]"
            )
            return

        if extended:
            self._format_extended_report(session, author, publications)
        else:
            self._format_publication_table(session, author, publications)

    def _format_extended_report(
        self, session: Session, author: Author, publications: List[Publication]
    ) -> None:
        """Render the extended per-paper view with quarterly citation charts."""
        self.console.print(
            f"\n[bold]Extended Citation Report — [cyan]{author.forename} {author.surname}[/cyan][/bold]"
        )

        for i, pub in enumerate(publications):
            self.console.print()
            self.console.print(Rule(style="dim"))
            self._format_extended_paper(session, author, pub, i + 1, len(publications))

        self.console.print()
        self.console.print(Rule(style="dim"))

        # Summary statistics (mirrors _format_publication_table)
        total_publications = len(publications)
        total_citations = sum(p.citation_count or 0 for p in publications)
        self.console.print(f"\n[bold]Summary Statistics:[/bold]")
        self.console.print(f"Total Publications: [green]{total_publications}[/green]")
        self.console.print(f"Total Citations: [green]{total_citations}[/green]")
        if total_publications > 0:
            avg = total_citations / total_publications if total_citations > 0 else 0.0
            self.console.print(
                f"Average Citations per Publication: [green]{avg:.2f}[/green]"
            )
            citation_counts = sorted(
                [p.citation_count or 0 for p in publications], reverse=True
            )
            h_index = sum(1 for i, c in enumerate(citation_counts) if c >= i + 1)
            self.console.print(f"H-index: [green]{h_index}[/green]")

    def _format_extended_paper(
        self,
        session: Session,
        author: Author,
        pub: Publication,
        pub_num: int,
        total_pubs: int,
    ) -> None:
        """Render details and quarterly citation chart for a single publication."""
        # Year and citations-per-year
        year_display = "-"
        years_since_pub = None
        if pub.pubdate:
            try:
                parts = pub.pubdate.split("T")[0].split("-")
                year = int(parts[0])
                year_display = str(year)
                month = int(parts[1]) if len(parts) > 1 else 1
                month = month if month != 0 else 1
                pub_dt = datetime.datetime(year, month, 1)
                years_since_pub = max(
                    (datetime.datetime.now() - pub_dt).days / 365.25, 1 / 12.0
                )
            except (ValueError, IndexError, TypeError):
                pass

        per_year_str = "-"
        if years_since_pub and pub.citation_count:
            per_year_str = f"{pub.citation_count / years_since_pub:.1f}"

        # Recent 90-day citations
        ninety_days_ago = datetime.datetime.now() - datetime.timedelta(days=90)
        recent = 0
        for c in session.query(Citation).filter_by(publication_id=pub.id).all():
            if not c.publication_date:
                continue
            try:
                parts = c.publication_date.split("T")[0].split("-")
                y = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 else 1
                m = m if m != 0 else 1
                d = int(parts[2]) if len(parts) > 2 else 1
                d = d if d != 0 else 1
                if datetime.datetime(y, m, d) >= ninety_days_ago:
                    recent += 1
            except (ValueError, IndexError, TypeError):
                pass

        position = self._find_author_position(pub.authors, author.surname, author.forename)
        ads_link = f"https://ui.adsabs.harvard.edu/abs/{pub.bibcode}/abstract"

        self.console.print(
            f"[bold cyan]Paper {pub_num} of {total_pubs}[/bold cyan]  [dim]ID: {pub.id}[/dim]"
        )
        self.console.print(f"[bold]{pub.title}[/bold]")
        self.console.print(f"[blue]{ads_link}[/blue]")
        self.console.print(
            f"[yellow]{year_display}[/yellow]  ·  "
            f"Position: [green]{position}[/green]  ·  "
            f"Citations: [green]{pub.citation_count or 0}[/green]  ·  "
            f"Last 90d: [green]{recent}[/green]  ·  "
            f"Per year: [green]{per_year_str}[/green]"
        )
        self.console.print("\n[bold]Citations per quarter:[/bold]")
        self._render_quarter_chart(session, pub)

    def _render_quarter_chart(self, session: Session, pub: Publication) -> None:
        """Render a horizontal Unicode bar chart of citations per quarter."""
        citations = session.query(Citation).filter_by(publication_id=pub.id).all()

        if not citations:
            self.console.print("[dim]  No citations recorded yet.[/dim]")
            return

        # Bin by (year, quarter)
        quarter_counts: collections.defaultdict = collections.defaultdict(int)
        for c in citations:
            if not c.publication_date:
                continue
            try:
                parts = c.publication_date.split("T")[0].split("-")
                year = int(parts[0])
                month = int(parts[1]) if len(parts) > 1 else 1
                month = month if month != 0 else 1
                quarter_counts[(year, (month - 1) // 3 + 1)] += 1
            except (ValueError, IndexError, TypeError):
                continue

        if not quarter_counts:
            self.console.print("[dim]  No dated citations found.[/dim]")
            return

        # Determine range
        start_q = None
        if pub.pubdate:
            try:
                parts = pub.pubdate.split("T")[0].split("-")
                py = int(parts[0])
                pm = int(parts[1]) if len(parts) > 1 else 1
                pm = pm if pm != 0 else 1
                start_q = (py, (pm - 1) // 3 + 1)
            except (ValueError, IndexError, TypeError):
                pass
        if start_q is None:
            start_q = min(quarter_counts)

        now = datetime.datetime.now()
        end_q = (now.year, (now.month - 1) // 3 + 1)

        # Walk every quarter from start to end
        quarters = []
        y, q = start_q
        while (y, q) <= end_q:
            quarters.append((y, q))
            q += 1
            if q > 4:
                q, y = 1, y + 1

        max_count = max(quarter_counts.values(), default=1)
        bar_width = 30
        q_labels = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}

        for (year, quarter) in reversed(quarters):
            count = quarter_counts.get((year, quarter), 0)
            label = f"{year} {q_labels[quarter]}"
            bar_len = int(round(count / max_count * bar_width)) if count > 0 else 0
            line = Text()
            line.append(f"  {label:<8}", style="dim")
            line.append("  ")
            line.append("█" * bar_len, style="green")
            line.append(f"  {count}")
            self.console.print(line)

    def _find_author_position(
        self, author_list_str: Optional[str], surname: str, forename: str
    ) -> str:
        """
        Find the position of the author in the author list.

        Parameters
        ----------
        author_list_str : str or None
            Semicolon-separated string of authors.
        surname : str
            Author's surname.
        forename : str
            Author's forename.

        Returns
        -------
        str
            Position string like "1st", "2nd", "Last", etc.
        """
        if not author_list_str:
            return "?"

        # Parse the author list
        authors = [a.strip() for a in author_list_str.split(";")]
        
        if not authors:
            return "?"

        # Look for exact match or close match
        target_name = f"{surname}, {forename}"
        
        for i, author_name in enumerate(authors):
            # Check for exact match or surname match
            if target_name.lower() in author_name.lower() or surname.lower() in author_name.lower():
                position = i + 1
                total = len(authors)
                
                # Handle special cases
                if position == 1:
                    return "1st"
                elif position == 2:
                    return "2nd"
                elif position == 3:
                    return "3rd"
                else:
                    return f"{position}th"
        
        return "?"

    def _format_publication_table(
        self, session: Session, author: Author, publications: List[Publication]
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

        total_citations = 0
        total_publications = len(publications)

        for pub in publications:
            # Get recent citations (last 90 days)
            ninety_days_ago_str = (
                datetime.datetime.now() - datetime.timedelta(days=90)
            ).strftime("%Y-%m-%d")

            recent_citations = 0
            citing_papers = (
                session.query(Citation).filter_by(publication_id=pub.id).all()
            )
            for citing_paper in citing_papers:
                try:
                    if citing_paper.publication_date:
                        date_only_str = citing_paper.publication_date.split("T")[0]

                        citing_paper_date_parts = date_only_str.split("-")
                        citing_year = int(citing_paper_date_parts[0])

                        citing_month = 1
                        if len(citing_paper_date_parts) > 1:
                            month_val = int(citing_paper_date_parts[1])
                            citing_month = month_val if month_val != 0 else 1

                        citing_day = 1
                        if len(citing_paper_date_parts) > 2:
                            day_val = int(citing_paper_date_parts[2])
                            citing_day = day_val if day_val != 0 else 1

                        citing_date_obj = datetime.datetime(
                            citing_year, citing_month, citing_day
                        )
                        ninety_days_ago_obj = datetime.datetime.strptime(
                            ninety_days_ago_str, "%Y-%m-%d"
                        )

                        if citing_date_obj >= ninety_days_ago_obj:
                            recent_citations += 1
                except (ValueError, IndexError, TypeError) as e:
                    logger.debug(
                        f"Could not parse date '{citing_paper.publication_date}' for recent citation check: {e}"
                    )
                    pass

            # Create ADS link
            ads_link = f"https://ui.adsabs.harvard.edu/abs/{pub.bibcode}/abstract"

            # Calculate years since publication
            years_since_pub = None
            year_display = "-"
            if pub.pubdate:
                try:
                    date_part = pub.pubdate.split("T")[0]
                    pub_date_parts = date_part.split("-")

                    year = int(pub_date_parts[0])
                    year_display = str(year)

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
                except (ValueError, IndexError, TypeError) as e:
                    logger.debug(
                        f"Could not parse pubdate '{pub.pubdate}' for years_since_pub calculation: {e}"
                    )
                    years_since_pub = None

            citations_per_year_str = "-"
            if years_since_pub is not None and pub.citation_count is not None:
                if years_since_pub > 0:
                    citations_per_year = pub.citation_count / years_since_pub
                    citations_per_year_str = f"{citations_per_year:.1f}"
                elif pub.citation_count > 0:
                    if years_since_pub < (1 / 12.0) and years_since_pub > 0:
                        citations_per_year_str = (
                            f"{pub.citation_count / years_since_pub:.1f}*"
                        )
                    else:
                        citations_per_year_str = "N/A"
                else:
                    citations_per_year_str = "0.0"

            # Format title
            title_display = pub.title
            if len(title_display) > 38:
                title_display = title_display[:35] + "..."

            # Find author position
            author_position = self._find_author_position(
                pub.authors, author.surname, author.forename
            )

            # Format citation info
            cite_info = f"{pub.citation_count or 0} ({recent_citations}) ({citations_per_year_str})"

            table.add_row(
                str(pub.id),
                author_position,
                title_display,
                cite_info,
                year_display,
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
            avg_citations = (
                total_citations / total_publications if total_citations > 0 else 0.0
            )
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
