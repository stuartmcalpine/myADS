"""Command-line interface for the citation tracker."""

import argparse
import logging
import os
from typing import Dict, Any

from myads.cite_tracker import CitationTracker


# CLI handler functions
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
        deep=args.get("deep", False),
    )


def generate_report_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for generating reports."""
    tracker.generate_report(
        author_id=args.get("author_id"), show_ignored=args.get("show_ignored", False)
    )


def ignore_publication_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for ignoring a publication."""
    tracker.ignore_publication(
        publication_id=args["publication_id"], reason=args.get("reason")
    )


def unignore_publication_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for unignoring a publication."""
    tracker.unignore_publication(publication_id=args["publication_id"])


def list_ignored_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for listing ignored publications."""
    tracker.list_ignored_publications(author_id=args.get("author_id"))


def clear_rejected_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for clearing rejected papers."""
    tracker.clear_rejected_papers(author_id=args.get("author_id"))


def list_rejected_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for listing rejected papers."""
    tracker.list_rejected_papers(author_id=args.get("author_id"))


def search_cli(tracker: CitationTracker, args: Dict[str, Any]) -> None:
    """CLI handler for searching author publications."""
    tracker.search_author_publications(
        surname=args["surname"],
        forename=args["forename"],
        orcid=args.get("orcid"),
        max_rows=args.get("max_rows", 100),
        sort=args.get("sort", "citation_count desc"),
        output_format=args.get("format", "table"),
        include_stats=not args.get("no_stats", False),
        first_author_only=args.get("first_author_only", False),
    )


def main():
    """Main entry point for the citation tracker CLI."""
    parser = argparse.ArgumentParser(description="ADS Citation Tracker")
    parser.add_argument(
        "--db-path",
        help="Path to database file (default: $MYADS_DATABASE_PATH or ~/.local/share/myads/database.db)",
    )
    subparsers = parser.add_subparsers(
        dest="command", help="Command to run", required=True
    )

    # Add author command
    add_author_parser = subparsers.add_parser(
        "add-author", help="Add author to database for citation tracking"
    )
    add_author_parser.add_argument("forename", help="Author first name")
    add_author_parser.add_argument("surname", help="Author last name")
    add_author_parser.add_argument("--orcid", help="ORCID identifier (enables tracking papers at any author position)")

    # Remove author command
    remove_author_parser = subparsers.add_parser(
        "remove-author", help="Remove author from tracking database"
    )
    remove_author_parser.add_argument(
        "author_id", type=int, help="Author ID to remove (see list-authors)"
    )

    # List authors command
    subparsers.add_parser("list-authors", help="Show all tracked authors and their IDs")

    # Add token command
    add_token_parser = subparsers.add_parser("add-token", help="Set ADS API token for queries")
    add_token_parser.add_argument("token", help="Your ADS API token")

    # Check citations command
    check_parser = subparsers.add_parser("check", help="Update publications and check for new citations")
    check_parser.add_argument(
        "--author-id", type=int, help="Check specific author ID only (default: all authors)"
    )
    check_parser.add_argument(
        "--max-rows",
        type=int,
        default=2000,
        help="Maximum results per ADS query",
    )
    check_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show updated citations in addition to new citations",
    )
    check_parser.add_argument(
        "--deep",
        action="store_true",
        help="Find additional co-authored papers not captured by ORCID search using name matching; requires manual confirmation",
    )

    # Generate report command
    report_parser = subparsers.add_parser("report", help="Display citation statistics and tracked publications")
    report_parser.add_argument(
        "--author-id", type=int, help="Report on specific author ID only (default: all authors)"
    )
    report_parser.add_argument(
        "--show-ignored",
        action="store_true",
        help="Include ignored publications in output",
    )

    # Ignore publication command
    ignore_parser = subparsers.add_parser(
        "ignore", help="Exclude publication from tracking and reports"
    )
    ignore_parser.add_argument(
        "publication_id", type=int, help="Publication ID to ignore (see report)"
    )
    ignore_parser.add_argument("--reason", help="Optional reason for ignoring")

    # Unignore publication command
    unignore_parser = subparsers.add_parser(
        "unignore", help="Re-enable tracking for previously ignored publication"
    )
    unignore_parser.add_argument(
        "publication_id", type=int, help="Publication ID to restore (see list-ignored)"
    )

    # List ignored publications command
    list_ignored_parser = subparsers.add_parser(
        "list-ignored", help="Show all ignored publications"
    )
    list_ignored_parser.add_argument(
        "--author-id",
        type=int,
        help="Filter by specific author ID (default: all authors)",
    )

    # Clear rejected papers command
    clear_rejected_parser = subparsers.add_parser(
        "clear-rejected", help="Reset rejected papers to be re-prompted in future deep checks"
    )
    clear_rejected_parser.add_argument(
        "--author-id",
        type=int,
        help="Filter by specific author ID (default: all authors)",
    )

    # List rejected papers command
    list_rejected_parser = subparsers.add_parser(
        "list-rejected", help="Show papers rejected during deep check"
    )
    list_rejected_parser.add_argument(
        "--author-id",
        type=int,
        help="Filter by specific author ID (default: all authors)",
    )

    # Search command (new one-off search)
    search_parser = subparsers.add_parser(
        "search", help="Query ADS for author publications without saving to database"
    )
    search_parser.add_argument("forename", help="Author first name")
    search_parser.add_argument("surname", help="Author last name")
    search_parser.add_argument("--orcid", help="ORCID identifier to restrict results (uses AND logic)")
    search_parser.add_argument(
        "--max-rows", type=int, default=100, help="Maximum results to return"
    )
    search_parser.add_argument(
        "--sort", default="citation_count desc", help="Sort order for results"
    )
    search_parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format: table (pretty), json, or csv",
    )
    search_parser.add_argument(
        "--no-stats", action="store_true", help="Skip summary statistics (table format only)"
    )
    search_parser.add_argument(
        "--first-author-only",
        action="store_true",
        help="Restrict to first-author papers only (default: any position)",
    )

    # Parse arguments
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO").upper())

    # Create tracker with optional custom database path
    tracker = CitationTracker(database_path=args.db_path)

    # Run command
    command_map = {
        "add-author": add_author_cli,
        "remove-author": remove_author_cli,
        "list-authors": list_authors_cli,
        "add-token": add_token_cli,
        "check": check_citations_cli,
        "report": generate_report_cli,
        "ignore": ignore_publication_cli,
        "unignore": unignore_publication_cli,
        "list-ignored": list_ignored_cli,
        "clear-rejected": clear_rejected_cli,
        "list-rejected": list_rejected_cli,
        "search": search_cli,
    }

    command_handler = command_map.get(args.command)
    if command_handler:
        command_handler(tracker, vars(args))


if __name__ == "__main__":
    main()
