# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

```bash
pip install -e ".[dev]"   # Install with dev dependencies (pytest, black, ruff, mypy)
pip install -e ".[viz]"   # Install with visualization dependencies (matplotlib, seaborn, wordcloud)
```

## Commands

```bash
# Run all tests
pytest tests/

# Run a specific test file
pytest tests/test_database.py -v

# Run a single test
pytest tests/test_database.py::test_add_author -v

# Lint / format
ruff check src/
black src/
mypy src/
```

## Architecture

The package has two layers:

### 1. ADS API layer (`src/myads/query.py`)
- `ADSQueryWrapper` — authenticated HTTP client for the NASA ADS API. Handles retries, pagination (`get_all_results`), and rate-limit tracking. Exposes `get()`, `citations()`, `references()`, `search_author()`.
- `ADSQuery` — wraps a single API response; builds a `papers_dict` and a pandas `DataFrame` with computed columns (ADS link, years since publication, citations/year). Iterating via `.papers` yields `ADSPaper` objects.
- `src/myads/__init__.py` re-exports `ADSQueryWrapper`, `ADSQuery` and `ADSPaper`.

### 2. Citation tracker (`src/myads/cite_tracker/`)
- **`tracker.py` — `CitationTracker`**: The central orchestrator. Holds a `DatabaseManager` and lazily initialises an `ADSQueryWrapper` from the stored token. All public operations (add/remove author, check citations, generate report, search) are methods here; heavy logic is delegated to focused manager classes.
- **`database.py` — `DatabaseManager`**: Creates the SQLAlchemy engine and provides `session_scope()` context manager (commit/rollback/close).
- **`models.py`**: SQLAlchemy ORM models — `Author`, `Publication`, `Citation`, `RejectedPaper`, `ADSToken`. Cascade deletes flow from `Author` down.
- **`publications.py` — `PublicationManager`**: Fetches/syncs an author's publications from ADS; handles ORCID vs. name-only search strategies and the interactive deep-check flow.
- **`citations.py` — `CitationManager`**: Compares stored citations against ADS results, persists new citations, and displays diffs.
- **`reports.py` — `ReportGenerator`**: Renders Rich tables with citation stats (h-index, per-year rate, recent-90-day count).
- **`search.py` — `SearchManager`**: One-off ADS search with table/JSON/CSV output, no database writes.
- **`utils.py`**: Shared helpers — ADS date parsing, h-index, ordinals, ADS links, truncation.
- **`constants.py`**: Resolves the default database path (env var `MYADS_DATABASE_PATH` → XDG `~/.local/share/myads/database.db` → legacy `~/myADS_database.db`).

### CLI (`src/myads/scripts/cite_tracker.py`)
Thin argparse layer; creates a `CitationTracker` and dispatches to `*_cli` handler functions. Entry point is `myads` (defined in `pyproject.toml`). Accepts a global `--db-path` flag.

## Testing Notes

Tests use a `temp_db` fixture (temporary SQLite file, auto-cleaned). Most tests do **not** make real ADS API calls — they use a `mock_ads_token` fixture and mock the HTTP layer. The `MYADS_DATABASE_PATH` and `XDG_DATA_HOME` env vars are cleared in the `temp_env` fixture to avoid polluting the live database during testing.
