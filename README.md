# 📚 myADS

`myADS` is a lightweight Python package to **track citations** to your (or others') research papers via the [NASA ADS API](https://ui.adsabs.harvard.edu/).

It helps you:
- 📈 Report an author's **current citation stats**.
- 🔎 Detect **new** or **updated citations** since the last check.
- 🧹 Maintain a local, efficient database for fast querying.

---

## 🚀 Installation

Install from [PyPI](https://pypi.org/project/myads/) with:

```bash
pip install myads
```

Or install from source:

```bash
git clone https://github.com/stuartmcalpine/myADS.git
cd myADS
pip install .
```

---

## 🛠 Getting Started

No manual database setup needed — it initializes automatically at `$HOME/myADS_database.db` the first time you run a command.

### 1. Add Your ADS API Token

First, get your token [here](https://ui.adsabs.harvard.edu/user/settings/token).

Then add it:

```bash
myads add-token YOUR-ADS-API-TOKEN
```

---

### 2. Add Authors to Track

Add an author by their name:

```bash
myads add-author "FirstName" "LastName" --orcid ORCID-ID
```

- `--orcid` is optional but highly recommended for accuracy.
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

(Find `AUTHOR_ID` by listing authors.)

---

## 📊 Usage

### Check for New Citations

```bash
myads check
```

- Checks for any **new** or **updated** citations to your tracked papers.
- You can target a specific author:

```bash
myads check --author-id 1
```

- See more detail (including updated citations):

```bash
myads check --verbose
```

---

### Generate a Citation Report

```bash
myads report
```

- Displays a report with:
  - 📈 Total citations
  - 🔥 Recent citations (last 90 days)
  - 🕒 Citations per year
  - 📅 Publication date
  - 📎 Direct ADS links

You can generate a report for a specific author:

```bash
myads report --author-id 1
```

---

### Example Output: Citation Report

```
Citation Report for Jane Doe
───────────────────────────────────────────────────────────────────────────────
Title                                Citations (last 90 days) [per year]  Date     ADS Link
───────────────────────────────────────────────────────────────────────────────
Galaxy Mergers and Black Hole Growth 52 (5) [10.3]                       2020-06  [link]
New Dark Matter Clues               10 (9) [45.0]                       2024-01  [link]
───────────────────────────────────────────────────────────────────────────────

Summary Statistics:
Total Publications: 2
Total Citations: 62
Average Citations per Publication: 31.00
H-index: 2
```

---

## 🧩 Command Overview

| Command | Purpose |
|:--------|:--------|
| `myads add-author "First" "Last" [--orcid ORCID-ID]` | Add a new author |
| `myads remove-author AUTHOR_ID` | Remove an author |
| `myads list-authors` | List all tracked authors |
| `myads add-token YOUR-TOKEN` | Add or update your ADS API token |
| `myads check [--author-id ID] [--verbose]` | Check for new/updated citations |
| `myads report [--author-id ID]` | Generate citation reports |

---

## 📦 How it Works

- **Local Database**: 
  - `myADS` uses an SQLite database to track publications, citations, and authors.
  - Efficiently updates and minimizes API calls.

- **Smart Citation Metrics**:
  - **Recent citations** are based on citing papers **published** in the last 90 days.
  - **Citations per year** are computed dynamically.
  - **H-index** is estimated automatically.

- **Automatic Resilience**:
  - Auto-handles expired ADS tokens.
  - Auto-creates the database if it doesn't exist.

---

## 🔥 Tips

- Adding ORCIDs increases precision and avoids name ambiguity.
- Set up a cron job or scheduled task to run `myads check` weekly!
- You can track multiple authors — perfect for research groups.

---

## 🛡 Disclaimer

This tool queries the NASA/ADS database under fair-use API limits.  
Make sure you have appropriate permissions and token access.

---

## 🧠 License

MIT License.

---

Made with ❤️ for astronomers and researchers by [Stuart McAlpine](https://github.com/stuartmcalpine).
