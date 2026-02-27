# myADS

myADS is a lightweight Python package to track citations to your (or others') research papers via the NASA ADS API.

It helps you:
- Report an author's current citation stats with author position and publication IDs
- Detect new or updated citations since the last check
- Find missing papers with deep search (any author position)
- Search for any author's publications without database tracking
- Maintain a local, efficient database for fast querying

## Installation

Install from PyPI with:

```bash
pip install myads
```

Or install from source:

```bash
git clone https://github.com/stuartmcalpine/myADS.git
cd myADS
pip install .
```

## Getting Started

No manual database setup needed — it initializes automatically at $HOME/myADS_database.db the first time you run a command.

### 1. Add Your ADS API Token

First, get your token [here](https://ui.adsabs.harvard.edu/user/settings/token).

Then add it:

```bash
myads add-token YOUR-ADS-API-TOKEN
```

### 2. Add Authors to Track

Add an author by their name:

```bash
myads add-author "FirstName" "LastName" --orcid ORCID-ID
```

**About ORCID:**
- Optional but highly recommended to avoid name ambiguity
- Enables tracking papers at any author position (where ORCID is attached in ADS)
- Without ORCID, only first-author papers are tracked by default

Example:

```bash
myads add-author "Jane" "Doe" --orcid 0000-0002-1825-0097
```

You can list authors you've added:

```bash
myads list-authors
```

Remove an author:

```bash
myads remove-author AUTHOR_ID
```

(Find AUTHOR_ID by listing authors.)

## Usage

### Check for New Citations

```bash
myads check
```

- Checks for any new or updated citations to your tracked papers
- You can target a specific author:

```bash
myads check --author-id 1
```

- See more detail (including updated citations):

```bash
myads check --verbose
```

- **Deep check** to find co-authored papers not captured by ORCID search (uses name matching):

```bash
myads check --deep --author-id 1
```

This finds papers where the author appears at any position but the ORCID isn't attached in ADS, or for authors without ORCID who want to track co-authored work. You'll be prompted to confirm each candidate paper. Papers you reject are remembered, so you won't be asked again. To reset this memory:

```bash
myads clear-rejected --author-id 1
```

**Note:** During `myads check`, you may be prompted to remove papers that exist in your local database but are no longer found in ADS results. This typically happens when author metadata is corrected in ADS, ORCIDs are updated, or papers are retracted. Answer 'n' to keep the paper if you know it's yours, or use `myads ignore` to exclude it from tracking.

### Generate a Citation Report

```bash
myads report
```

- Displays a report with:
  - Publication ID (for ignoring papers)
  - Author position (1st, 2nd, Last, etc.)
  - Total citations
  - Recent citations (last 90 days)
  - Citations per year
  - Publication year
  - Direct ADS links

You can generate a report for a specific author:

```bash
myads report --author-id 1
```

For a detailed per-paper breakdown including a quarterly citation timeline, use `--extended`:

```bash
myads report --extended
```

### Ignore Publications

Mark conference proceedings, theses, or other papers you don't want to track:

```bash
myads ignore PUBLICATION_ID --reason "conference proceedings"
```

View ignored papers:

```bash
myads list-ignored
```

Restore tracking:

```bash
myads unignore PUBLICATION_ID
```

### Search Without Tracking

Search for any author's publications without adding them to your database:

```bash
myads search "Jane" "Doe"
```

Options:
- `--orcid ORCID-ID` - Restrict results to papers matching both ORCID and author name (AND logic)
- `--first-author-only` - Restrict to first author papers only
- `--format {table,json,csv}` - Output format
- `--max-rows N` - Number of results (default: 100)

Example:
```bash
myads search "Jane" "Doe" --orcid 0000-0002-1825-0097 --format csv > output.csv
```

## Command Overview

| Command | Purpose |
|:--------|:--------|
| myads add-author "First" "Last" [--orcid ORCID] | Add a new author |
| myads remove-author AUTHOR_ID | Remove an author |
| myads list-authors | List all tracked authors |
| myads add-token YOUR-TOKEN | Add or update your ADS API token |
| myads check [--author-id ID] [--verbose] [--deep] | Check for new/updated citations |
| myads report [--author-id ID] [--show-ignored] [--extended] [--id ID ...] | Generate citation reports |
| myads ignore PUBLICATION_ID [--reason TEXT] | Mark publication as ignored |
| myads unignore PUBLICATION_ID | Restore tracking for publication |
| myads list-ignored [--author-id ID] | List ignored publications |
| myads clear-rejected [--author-id ID] | Clear deep check rejection memory |
| myads list-rejected [--author-id ID] | View rejected papers from deep check |
| myads search "First" "Last" [--orcid ORCID] [--first-author-only] | One-off author search |

## How it Works

**Local Database**: 
myADS uses an SQLite database to track publications, citations, and authors. This approach efficiently updates data and minimizes API calls.

**Smart Citation Metrics**:
- Recent citations are based on citing papers published in the last 90 days
- Citations per year are computed dynamically
- H-index is estimated automatically
- Author position is determined from the full author list

**Deep Search**:
Default tracking behavior depends on ORCID: with ORCID, myADS tracks papers at any author position (where ORCID is attached in ADS) plus first-author papers by name; without ORCID, only first-author papers are tracked. Use `--deep` to find additional co-authored papers not captured by ORCID search, with interactive confirmation to avoid false matches.

**Automatic Resilience**:
- Auto-handles expired ADS tokens
- Auto-creates the database if it doesn't exist

## Tips

- Adding ORCIDs enables tracking at any author position (not just first author) and avoids name ambiguity
- Use `--deep` periodically to catch co-authored papers where ORCID wasn't properly linked in ADS
- Ignore conference proceedings or other non-article publications to clean up your reports
- Use `myads search` to quickly check someone's work without adding them to your database
- Set up a cron job or scheduled task to run `myads check` weekly
- You can track multiple authors — perfect for research groups

## Troubleshooting

### Database Location

By default, myADS stores its database at:
- `~/.local/share/myads/database.db` (XDG spec, recommended)
- `~/myADS_database.db` (legacy location, if it already exists)

**Customize location:**
```bash
# Using environment variable
export MYADS_DATABASE_PATH=/custom/path/myads.db
myads check

# Using command-line flag
myads --db-path /custom/path/myads.db check
```

**For development:**
```bash
pip install -e ".[dev]"  # Install with dev dependencies (pytest, black, ruff, mypy)
pip install -e ".[viz]"  # Install with visualization dependencies for notebooks
```

**Running tests:**
```bash
pytest tests/        # Run all tests
pytest tests/ -v     # Verbose output
```

### No Publications Found

If `myads check` or `myads search` returns no results:

**With ORCID:**
- Verify your ORCID is correct on [orcid.org](https://orcid.org)
- Check that ADS has linked your ORCID to your papers
- Verify name spelling matches ADS records
- Try `--deep` to find papers without ORCID metadata

**Without ORCID:**
- Only first-author papers are tracked by default
- Add an ORCID for better coverage
- Use `--deep` to search all author positions
- Check name spelling and format (e.g., "Last, First")

### Paper Removal Prompts

During `myads check`, you may be prompted to remove papers not found in current ADS results.

**Common causes:**
- Author metadata corrected in ADS (name spelling changed)
- ORCID associations updated or removed
- Paper retracted or moved to different collection
- Your search criteria changed (e.g., added ORCID)

**What to do:**
- Answer 'n' to keep the paper if you know it's yours
- Use `myads ignore <pub_id>` to keep but exclude from tracking
- Answer 'y' to remove if it was incorrectly added

### Rate Limits

ADS API has daily rate limits. If you hit the limit:
- Reduce `--max-rows` to fetch fewer results
- Wait 24 hours for limit reset
- Check remaining calls: the tool displays this after each run

## Disclaimer

This tool queries the NASA/ADS database under fair-use API limits. Make sure you have appropriate permissions and token access.

## License

MIT License.

---

Made for astronomers and researchers by [Stuart McAlpine](https://github.com/stuartmcalpine).
