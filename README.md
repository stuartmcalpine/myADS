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

- `--orcid` is optional but highly recommended for accuracy
- Example:

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

- **Deep check** to find papers where the author appears in any position (not just first author):

```bash
myads check --deep --author-id 1
```

The deep check will prompt you to confirm each candidate paper. Papers you reject are remembered, so you won't be asked again. To reset this memory:

```bash
myads clear-rejected --author-id 1
```

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
- `--orcid ORCID-ID` - Include ORCID in search
- `--first-author-only` - Restrict to first author papers only
- `--format {table,json,csv}` - Output format
- `--max-rows N` - Number of results (default: 100)

Example:
```bash
myads search "Jane" "Doe" --orcid 0000-0002-1825-0097 --format csv > output.csv
```

### Example Output: Citation Report

```
Citation Report for Jane Doe
─────────────────────────────────────────────────────────────────────────────────
ID  Pos  Title                              Citations  Year  ADS Link
                                            (90d)
                                            (per yr)
─────────────────────────────────────────────────────────────────────────────────
42  1st  Galaxy Mergers and Black Holes...  52         2020  [link]
                                            (5)
                                            (10.3)
15  3rd  Collaboration Paper...             10         2024  [link]
                                            (9)
                                            (45.0)
─────────────────────────────────────────────────────────────────────────────────

Summary Statistics:
Total Publications: 2
Total Citations: 62
Average Citations per Publication: 31.00
H-index: 2
```

## Command Overview

| Command | Purpose |
|:--------|:--------|
| myads add-author "First" "Last" [--orcid ORCID] | Add a new author |
| myads remove-author AUTHOR_ID | Remove an author |
| myads list-authors | List all tracked authors |
| myads add-token YOUR-TOKEN | Add or update your ADS API token |
| myads check [--author-id ID] [--verbose] [--deep] | Check for new/updated citations |
| myads report [--author-id ID] [--show-ignored] | Generate citation reports |
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
By default, myADS tracks papers where the author is first author. Use `--deep` to find papers where they appear in any position, with interactive confirmation to avoid false matches.

**Automatic Resilience**:
- Auto-handles expired ADS tokens
- Auto-creates the database if it doesn't exist

## Tips

- Adding ORCIDs increases precision and avoids name ambiguity
- Use `--deep` periodically to catch papers where ORCID wasn't properly linked
- Ignore conference proceedings or other non-article publications to clean up your reports
- Use `myads search` to quickly check someone's work without adding them to your database
- Set up a cron job or scheduled task to run `myads check` weekly
- You can track multiple authors — perfect for research groups

## Disclaimer

This tool queries the NASA/ADS database under fair-use API limits. Make sure you have appropriate permissions and token access.

## License

MIT License.

---

Made for astronomers and researchers by [Stuart McAlpine](https://github.com/stuartmcalpine).
