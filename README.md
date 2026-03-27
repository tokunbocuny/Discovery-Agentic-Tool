# BCC/CUNY Library Agentic Project

AI-powered library research tools for **Bronx Community College / CUNY**.
Includes a natural language search agent, Primo VE API connector, and Alma Analytics → Power BI bridge.

---

## Table of Contents

- [Web Search Agent (NEW)](#web-search-agent)
  - [Quick Start](#quick-start)
  - [How It Works](#how-it-works)
  - [Architecture](#architecture)
  - [File Reference](#file-reference)
- [Primo VE API Connector](#primo-ve-api-connector)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Usage](#usage)
  - [Pipeline Overview](#pipeline-overview)
  - [Example Output](#example-output)
  - [Getting Your API Key](#getting-your-api-key)
  - [Getting Your VID](#getting-your-vid)
- [What Are Boolean Operators?](#what-are-boolean-operators)
- [Core Operators](#core-operators)
- [Phrase-to-Boolean Breakdown Method](#phrase-to-boolean-breakdown-method)
- [Step-by-Step Examples](#step-by-step-examples)
- [Advanced Techniques](#advanced-techniques)
- [Database-Specific Notes](#database-specific-notes)
- [Quick Reference Cheat Sheet](#quick-reference-cheat-sheet)

---

## Web Search Agent

A browser-based search UI where staff type a natural language query, and a
**Claude agent** translates it into a boolean search, queries the Primo VE
catalog, and returns results with a natural language summary.

```
User types: "interlibrary loan trends in community colleges"
                            │
                            ▼
             Claude Agent SDK (uses Claude Code auth)
                            │
                  calls search_library_catalog tool
                            │
                            ▼
              Primo VE REST API  (api-na.hosted.exlibrisgroup.com)
                            │
                            ▼
              Claude summarises + returns structured results
                            │
                            ▼
               Browser renders cards + summary + boolean string
```

### Quick Start

**Prerequisites**

| Requirement | Version | Notes |
|---|---|---|
| Python | ≥ 3.10 | System Python 3.9 is too old; see [Python Setup](#python-setup) |
| Claude Code | Any | Must be logged in — the agent uses your existing session |
| Primo API key | — | Set in `.env` as `PRIMO_API_KEY` |

**Python Setup** (one-time, skip if you already have Python 3.10+)

```bash
# Install pyenv
git clone https://github.com/pyenv/pyenv.git ~/.pyenv
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.12
pyenv install 3.12

# Persist pyenv in your shell profile (add these lines to ~/.zshrc or ~/.bash_profile)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
```

**App Setup**

```bash
cd "Desktop/Agentic Project"

# Pin Python 3.12 for this project (already done — .python-version file)
# pyenv local 3.12

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

Open **http://localhost:8000** in your browser.

### How It Works

1. Staff enter a natural language query in the browser.
2. `app.py` (FastAPI) receives a `POST /search` request.
3. `agent.py` creates a per-request MCP tool wrapping `search_from_phrase()`
   from `primo_connector.py`.
4. The **Claude Agent SDK** sends the query to Claude with the tool available.
   Claude decides how to call it (choosing phrase, limit, sort).
5. The tool hits the Primo VE API and returns a concise text summary to Claude.
6. Claude writes a natural language summary of the results.
7. The API returns `{results, total, boolean_string, summary}` as JSON.
8. The frontend renders result cards and Claude's summary.

**Authentication** — the Agent SDK uses your existing Claude Code session.
No `ANTHROPIC_API_KEY` is needed in `.env`.

### Architecture

```
Agentic Project/
├── app.py                     ← FastAPI server (routes, request/response models)
├── agent.py                   ← Claude Agent SDK pipeline + MCP tool definition
├── primo_connector.py         ← Primo VE connector (unchanged)
├── alma_analytics_connector.py← Alma → Power BI connector (unchanged)
├── test_connectors.py         ← Test suite (primo connector, live API tests)
├── templates/
│   └── search.html            ← Single-page search UI (HTML/CSS/JS)
├── requirements.txt           ← Pinned dependencies
├── .env                       ← API keys (gitignored)
├── .env.example               ← Template for .env
└── .venv/                     ← Virtual environment (gitignored)
```

### File Reference

| File | Purpose |
|---|---|
| `app.py` | FastAPI app; endpoints: `GET /`, `POST /search`, `GET /health` |
| `agent.py` | Agent SDK pipeline; `run_search(query, limit, sort) → dict` |
| `primo_connector.py` | Primo VE connector; imported by agent.py without modification |
| `templates/search.html` | Browser UI; calls `POST /search` via `fetch()` |
| `requirements.txt` | All Python dependencies with comments |

**Endpoints**

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Search UI |
| `POST` | `/search` | Run agent search; body: `{query, limit, sort}` |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Auto-generated FastAPI docs |

**Running on a different port**

```bash
uvicorn app:app --port 8080 --reload
```

**Running the Alma connector server on port 8765** (separate terminal)

```bash
python alma_analytics_connector.py --serve
```

---

---

## Primo VE API Connector

`primo_connector.py` is a Python script that takes any natural language research phrase, breaks it into concepts, builds a boolean string, and queries the **BCC / CUNY OneSearch Primo VE REST API** — all in one pipeline.

```
Natural language phrase
        │
        ▼
  Concept extraction   ──→  Synonym expansion
        │
        ▼
  Boolean string       ──→  Human-readable (AND/OR/NOT)
        │
        ▼
  Primo API query      ──→  q= parameter format
        │
        ▼
  Live search results  ──→  Title, Author, Date, Type, Link
```

---

### Prerequisites

- Python 3.10+ (required for `claude-agent-sdk`; 3.9 works for the connector alone)
- A free Ex Libris Developer Network account and API key
- Network access to CUNY API gateway (on-campus or VPN may be required)

---

### Installation

```bash
# 1. Clone or download this repository
git clone https://github.com/YOUR_USERNAME/boolean-search-builder.git
cd boolean-search-builder

# 2. Install dependencies
pip install requests python-dotenv
```

---

### Configuration

```bash
# 3. Copy the example environment file
cp .env.example .env

# 4. Open .env and fill in your credentials
```

Your `.env` file should look like:

```env
PRIMO_API_KEY=your_actual_api_key_here
PRIMO_VID=01CUNY_BX
PRIMO_SCOPE=MyInst_and_CI
PRIMO_TAB=Everything
```

> ⚠️ **Never commit your `.env` file.** It is already listed in `.gitignore`.

---

### Usage

**Run a search directly:**
```bash
python primo_connector.py
```

**Import as a module in your own script:**
```python
from primo_connector import search_from_phrase, save_results

# Search from a natural language phrase
response = search_from_phrase(
    "interlibrary loan trends in discovery systems at community colleges",
    limit=10,
    sort="date_d"   # newest first
)

# Save full JSON response
save_results(response, "my_search.json")
```

**Paginate through results:**
```python
# Page 1 (records 1–10)
search_from_phrase("Alma analytics resource sharing", limit=10, offset=0)

# Page 2 (records 11–20)
search_from_phrase("Alma analytics resource sharing", limit=10, offset=10)
```

**Sort options:**

| Value    | Description       |
|----------|-------------------|
| `rank`   | Relevance (default) |
| `date_d` | Newest first      |
| `date_a` | Oldest first      |
| `title`  | Alphabetical by title |
| `author` | Alphabetical by author |

---

### Pipeline Overview

The connector follows the same 4-step method documented in this README:

| Step | Function | Description |
|------|----------|-------------|
| 1 | `extract_concepts(phrase)` | Identifies known concepts from the phrase |
| 2 | `build_boolean_string(concepts)` | Produces a human-readable AND/OR boolean string |
| 3 | `build_primo_query(concepts)` | Converts to Primo VE `q=` parameter syntax |
| 4 | `search_primo(query)` | Sends GET request to Primo VE REST API |

To add new domain terms, extend the `SYNONYM_MAP` dictionary in `primo_connector.py`:

```python
SYNONYM_MAP["open access"] = ["open access", "OA", "freely available", "open scholarship"]
```

---

### Example Output

```
══════════════════════════════════════════════════════════════════════
  PHRASE   : interlibrary loan trends in discovery systems
══════════════════════════════════════════════════════════════════════

📌 Concepts identified: interlibrary loan, discovery systems

📖 Boolean String:

   ("interlibrary loan" OR "ILL" OR "resource sharing" OR "document delivery")
   AND ("discovery systems" OR "discovery layer" OR "web-scale discovery")

🔧 Primo API q= parameter:
   any,contains,interlibrary loan,OR;any,contains,ILL,OR;...

🔍 Querying Primo VE...
   Endpoint : https://api-na.hosted.exlibrisgroup.com/primo/v1/search
   VID      : 01CUNY_BX

✅ Results found : 47
   Showing       : 1–5
──────────────────────────────────────────────────────────────────────
  [1] Interlibrary loan and document delivery in the larger academic library
      Author : Boucher, Virginia
      Date   : 2022
      Type   : book
      Source : CUNY OneSearch
```

---

### Getting Your API Key

1. Go to [https://developers.exlibrisgroup.com](https://developers.exlibrisgroup.com)
2. Create a free account
3. Navigate to **Build → My APIs → Manage Keys → Add API Key**
4. Set permissions: **Primo → Search → Read only**
5. Choose environment: **Sandbox** (for testing) or **Production**
6. Copy the key into your `.env` file as `PRIMO_API_KEY`

---

### Getting Your VID

Your **View ID (VID)** identifies your specific Primo VE institutional view.

- Contact **CUNY Office of Library Services (OLS)**:
  - 🌐 [https://ols-support.cuny.edu](https://ols-support.cuny.edu)
  - ✉️ support@cuny-ols.libanswers.com
- **Confirmed BCC VID:** `01CUNY_BX`
- CUNY Network-wide: `01CUNY_NETWORK:CUNY_NETWORK`
- Find additional views in your Primo VE Back Office under **Views**

---

## What Are Boolean Operators?

Boolean operators are logical connectors used in database and search engine queries to combine, exclude, or relate search terms. The three core operators are:

| Operator | Function |
|----------|----------|
| `AND`    | Narrows results — both terms must be present |
| `OR`     | Broadens results — either term can be present |
| `NOT`    | Excludes results containing a term |

---

## Core Operators

### AND
Use `AND` to connect distinct concepts that must **all** appear in results.

```
interlibrary loan AND resource sharing AND academic libraries
```

### OR
Use `OR` to group **synonyms or related terms** so results include any variation.

```
"resource sharing" OR "interlibrary loan" OR ILL
```

### NOT
Use `NOT` (or `-` in some platforms) to **eliminate** irrelevant results.

```
library systems AND automation NOT MARC
```

### Quotation Marks `" "`
Use quotes to search for an **exact phrase** rather than individual words.

```
"access services" AND "discovery systems"
```

### Truncation `*`
Use an asterisk to capture **word variations** from a common root.

```
librar* → library, libraries, librarian, librarianship
```

### Wildcards `?`
Use `?` to substitute a **single character** within a word.

```
wom?n → woman, women
```

### Parentheses `( )`
Use parentheses to **group synonyms together** and control the order of operations.

```
(ILL OR "interlibrary loan" OR "resource sharing") AND (Alma OR Primo OR OCLC)
```

---

## Phrase-to-Boolean Breakdown Method

Follow this 4-step process to convert any research phrase into a searchable boolean string.

### Step 1 — Identify the Core Concepts
Break the phrase into its main ideas (usually 2–4 concepts).

> **Phrase:** "The impact of library discovery systems on interlibrary loan trends at community colleges"

| Concept 1 | Concept 2 | Concept 3 | Concept 4 |
|-----------|-----------|-----------|-----------|
| discovery systems | interlibrary loan | community colleges | impact / trends |

---

### Step 2 — Generate Synonyms and Variants for Each Concept
List alternate terms, abbreviations, and related phrases for each concept.

| Concept | Synonyms / Variants |
|---------|---------------------|
| discovery systems | "discovery layer", "web-scale discovery", Primo, Summon, EBSCO Discovery |
| interlibrary loan | ILL, "resource sharing", "document delivery" |
| community colleges | "two-year college", "junior college", "community college" |
| impact / trends | impact, trend*, effect*, analy* |

---

### Step 3 — Build OR Groups for Each Concept
Wrap each synonym cluster in parentheses connected with `OR`.

```
("discovery systems" OR "discovery layer" OR "web-scale discovery")

AND

(ILL OR "interlibrary loan" OR "resource sharing" OR "document delivery")

AND

("community college" OR "two-year college" OR "junior college")

AND

(impact OR trend* OR effect* OR analy*)
```

---

### Step 4 — Combine with AND
Join all concept groups with `AND`.

```
("discovery systems" OR "discovery layer" OR "web-scale discovery")
AND (ILL OR "interlibrary loan" OR "resource sharing" OR "document delivery")
AND ("community college" OR "two-year college" OR "junior college")
AND (impact OR trend* OR effect* OR analy*)
```

---

## Step-by-Step Examples

### Example 1: Library Access Services Leadership

**Phrase:** "Leadership and management in library access services"

**Step 1 — Core Concepts:**
- leadership / management
- access services
- library

**Step 2 — Synonyms:**

| Concept | Variants |
|---------|----------|
| leadership / management | leadership, manag*, administrat*, supervis* |
| access services | "access services", circulation, "reserves", "course reserves" |
| library | librar*, "academic library", "public library" |

**Step 3 — OR Groups:**

```
(leadership OR manag* OR administrat* OR supervis*)
AND ("access services" OR circulation OR reserves OR "course reserves")
AND (librar* OR "academic library")
```

---

### Example 2: Alma Analytics for Resource Sharing

**Phrase:** "Using Alma Analytics to improve resource sharing data reporting"

**Step 1 — Core Concepts:**
- Alma Analytics
- resource sharing
- data reporting

**Step 2 — Synonyms:**

| Concept | Variants |
|---------|----------|
| Alma Analytics | "Alma Analytics", "Ex Libris Alma", "library analytics" |
| resource sharing | "resource sharing", ILL, "interlibrary loan", "document delivery" |
| data reporting | "data reporting", "statistical reporting", "metrics", dashboard*, analyt* |

**Step 3 — Final String:**

```
("Alma Analytics" OR "Ex Libris Alma" OR "library analytics")
AND ("resource sharing" OR ILL OR "interlibrary loan" OR "document delivery")
AND ("data reporting" OR "statistical reporting" OR metrics OR dashboard* OR analyt*)
```

---

### Example 3: Copyright in Academic Libraries

**Phrase:** "Copyright compliance and fair use in academic library reserves"

**Step 1 — Core Concepts:**
- copyright
- fair use
- academic library
- reserves / course reserves

**Step 2 — Synonyms:**

| Concept | Variants |
|---------|----------|
| copyright | copyright, "intellectual property", "copyright law" |
| fair use | "fair use", "fair dealing", "copyright exemption" |
| academic library | "academic library", "university library", "college library" |
| reserves | reserves, "course reserves", "electronic reserves", "e-reserves" |

**Step 3 — Final String:**

```
(copyright OR "intellectual property" OR "copyright law")
AND ("fair use" OR "fair dealing" OR "copyright exemption")
AND ("academic library" OR "university library" OR "college library")
AND (reserves OR "course reserves" OR "electronic reserves" OR "e-reserves")
```

---

### Example 4: Interlibrary Loan Workflow Efficiency

**Phrase:** "Improving ILL request fulfillment and turnaround time"

```
(ILL OR "interlibrary loan" OR "resource sharing")
AND (fulfillment OR "request processing" OR workflow* OR "turnaround time")
AND (improv* OR efficien* OR optimiz* OR reduc*)
```

---

## Advanced Techniques

### Nesting Complex Queries

Use multiple levels of parentheses for compound searches.

```
((ILL OR "interlibrary loan") AND (Alma OR OCLC OR WorldShare))
AND ("academic library" OR "research library")
NOT "public library"
```

---

### Field-Specific Searching

Many databases support searching within specific fields using tags:

| Field | Common Tag Syntax |
|-------|-------------------|
| Title | `TI:`, `ti=`, `title:` |
| Abstract | `AB:`, `ab=` |
| Author | `AU:`, `au=` |
| Subject | `SU:`, `su=`, `MH:` |
| Journal | `SO:`, `jn=` |

**Example:**
```
TI:("interlibrary loan" OR "resource sharing") AND AB:(analytic* OR metric* OR data)
```

---

### Date Limiting

Append date ranges to narrow to recent literature:

```
("discovery systems" OR "web-scale discovery") AND ILL AND PY:2018-2025
```

---

### Proximity Operators

Some databases support proximity searching to find terms near each other:

| Operator | Platform | Meaning |
|----------|----------|---------|
| `W/n`    | EBSCOhost | within n words |
| `N/n`    | EBSCOhost | near (order doesn't matter) |
| `ADJ n`  | ProQuest  | adjacent within n words |

**Example (EBSCOhost):**
```
"library" W/3 "automation"
```

---

## Database-Specific Notes

| Database | Truncation | Wildcard | Phrase Search | Notes |
|----------|------------|----------|---------------|-------|
| EBSCOhost | `*` | `?` | `" "` | Supports `W/n` and `N/n` proximity |
| ProQuest | `*` | `?` | `" "` | Use `ADJ` for proximity |
| Web of Science | `*` | `?` | `" "` | Use `NEAR/n` for proximity |
| Google Scholar | — | — | `" "` | Limited boolean; use `"phrase" -exclude` |
| OCLC WorldCat | `*` | `?` | `" "` | Use `kw:` for keyword field |
| Primo / Ex Libris | `*` | — | `" "` | Facets available to filter post-search |

---

## Quick Reference Cheat Sheet

```
CONCEPT BREAKDOWN TEMPLATE
───────────────────────────────────────────────────────────
Phrase:  [Your research topic here]

Concept 1: _______________________________________________
  Synonyms: _______________ OR _______________ OR _______________

Concept 2: _______________________________________________
  Synonyms: _______________ OR _______________ OR _______________

Concept 3: _______________________________________________
  Synonyms: _______________ OR _______________ OR _______________

Final String:
  (synonym1a OR synonym1b OR synonym1c)
  AND (synonym2a OR synonym2b OR synonym2c)
  AND (synonym3a OR synonym3b OR synonym3c)
───────────────────────────────────────────────────────────

OPERATORS AT A GLANCE
  AND      → narrows (both must appear)
  OR       → broadens (either can appear)
  NOT      → excludes
  " "      → exact phrase
  *        → truncation (librar* = library, libraries, librarian)
  ?        → single character wildcard (wom?n = woman, women)
  ( )      → group synonyms, control order of operations
```

---

## Contributing

Found an example to add or a database-specific tip? Open an issue or submit a pull request.

---

*Maintained by Tokunbo Adeshina Jr. | Bronx Community College Library*
