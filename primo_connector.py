"""
primo_connector.py
──────────────────────────────────────────────────────────────────────────────
Bronx Community College – Primo VE API Connector
Converts natural language phrases into boolean search strings and queries
the CUNY OneSearch / Primo VE REST API.

Author : Tokunbo Adeshina Jr.
Institution: Bronx Community College, CUNY
API Docs   : https://developers.exlibrisgroup.com/primo/apis/search/

SETUP:
  1. Register at https://developers.exlibrisgroup.com and create an API key
     with "Primo" read access.
  2. Copy .env.example → .env and fill in your API key and VID.
  3. pip install requests python-dotenv
  4. python primo_connector.py
──────────────────────────────────────────────────────────────────────────────
"""

import os
import re
import json
import time
import requests
from typing import Optional
from dotenv import load_dotenv

# ── Load environment variables ────────────────────────────────────────────────
load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
# North America API gateway (BCC/CUNY is hosted in NA region)
BASE_URL    = "https://api-na.hosted.exlibrisgroup.com/primo/v1/search"

# Your API key from developers.exlibrisgroup.com
# Set in .env as:  PRIMO_API_KEY=your_key_here
API_KEY     = os.getenv("PRIMO_API_KEY", "YOUR_API_KEY_HERE")

# BCC Primo VE View ID — confirmed: 01CUNY_BX
# For the full CUNY network scope use: 01CUNY_NETWORK:CUNY_NETWORK
VID         = os.getenv("PRIMO_VID", "01CUNY_BX")

# Default search scope and tab (confirm with your Primo VE admin)
SCOPE       = os.getenv("PRIMO_SCOPE", "MyInst_and_CI")
TAB         = os.getenv("PRIMO_TAB",   "Everything")

# Number of results to return per request (max 50)
DEFAULT_LIMIT  = 10
DEFAULT_OFFSET = 0


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — PHRASE → CONCEPT BREAKDOWN
# ══════════════════════════════════════════════════════════════════════════════

# Synonym map: extend this dictionary with your own domain terms.
# Keys are normalized concept keywords; values are synonym lists.
SYNONYM_MAP: dict[str, list[str]] = {
    # Resource Sharing / ILL
    "interlibrary loan"  : ["interlibrary loan", "ILL", "resource sharing", "document delivery"],
    "resource sharing"   : ["resource sharing", "interlibrary loan", "ILL", "document delivery"],
    "document delivery"  : ["document delivery", "interlibrary loan", "ILL"],

    # Discovery Systems
    "discovery"          : ["discovery systems", "discovery layer", "web-scale discovery",
                             "Primo", "Summon", "EBSCO Discovery Service"],
    "discovery systems"  : ["discovery systems", "discovery layer", "web-scale discovery"],

    # Library Management
    "alma"               : ["Alma", "Ex Libris Alma", "library management system", "LMS", "ILS"],
    "analytics"          : ["analytics", "metrics", "reporting", "data analysis", "dashboard"],
    "access services"    : ["access services", "circulation", "reserves", "course reserves"],

    # Copyright / Scholarly Communication
    "copyright"          : ["copyright", "intellectual property", "copyright law"],
    "fair use"           : ["fair use", "fair dealing", "copyright exemption"],

    # Academic Library Types
    "academic library"   : ["academic library", "university library", "college library",
                             "research library"],
    "community college"  : ["community college", "two-year college", "junior college",
                             "community college library"],

    # Outcomes / Impact
    "impact"             : ["impact", "effect", "outcome", "influence"],
    "trend"              : ["trend", "trends", "pattern", "change over time"],
    "efficiency"         : ["efficiency", "effectiveness", "performance", "workflow"],
}


def extract_concepts(phrase: str) -> list[str]:
    """
    Naive concept extractor: splits a phrase into individual words/bigrams
    and matches them against the synonym map keys.

    Returns a list of matched concept keys.
    """
    phrase_lower = phrase.lower()
    matched = []

    # Check multi-word keys first (longest match wins)
    sorted_keys = sorted(SYNONYM_MAP.keys(), key=len, reverse=True)
    used_spans: list[tuple[int, int]] = []

    for key in sorted_keys:
        idx = phrase_lower.find(key)
        if idx == -1:
            continue
        end = idx + len(key)
        # Make sure this span doesn't overlap an already-matched span
        overlap = any(not (end <= s or idx >= e) for s, e in used_spans)
        if not overlap:
            matched.append(key)
            used_spans.append((idx, end))

    return matched


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — BUILD BOOLEAN STRING (human-readable)
# ══════════════════════════════════════════════════════════════════════════════

def build_boolean_string(concepts: list[str]) -> str:
    """
    Takes a list of concept keys and builds a human-readable boolean string
    using synonyms from SYNONYM_MAP.

    Example output:
        ("interlibrary loan" OR "ILL" OR "resource sharing")
        AND ("discovery systems" OR "discovery layer")
    """
    if not concepts:
        return ""

    groups = []
    for concept in concepts:
        synonyms = SYNONYM_MAP.get(concept, [concept])
        # Wrap multi-word terms in quotes
        quoted = [f'"{s}"' if " " in s else s for s in synonyms]
        group  = " OR ".join(quoted)
        if len(quoted) > 1:
            group = f"({group})"
        groups.append(group)

    return "\nAND ".join(groups)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — BUILD PRIMO VE API QUERY STRING
# ══════════════════════════════════════════════════════════════════════════════

def build_primo_query(concepts: list[str], raw_phrase: str = "") -> str:
    """
    Converts concept synonyms into Primo VE REST API `q` parameter syntax.

    Primo `q` format:
        field,search_type,value,OPERATOR|field,search_type,value
    The operator (AND/OR) is appended as a 4th comma-separated field on each
    segment EXCEPT the last one, and segments are joined with the pipe `|`
    delimiter.

    Example output:
        any,contains,interlibrary loan,OR|any,contains,ILL,OR|
        any,contains,resource sharing,AND|any,contains,discovery systems,OR|
        any,contains,discovery layer
    """
    if not concepts:
        safe = raw_phrase.replace('"', '')
        return f"any,contains,{safe}"

    # Build a flat list of (synonym, following_operator) pairs
    # following_operator is OR within a concept group, AND between groups,
    # and None for the very last synonym overall.
    pairs: list[tuple[str, str | None]] = []

    for i, concept in enumerate(concepts):
        synonyms = SYNONYM_MAP.get(concept, [concept])
        is_last_concept = (i == len(concepts) - 1)

        for j, synonym in enumerate(synonyms):
            is_last_synonym = (j == len(synonyms) - 1)

            if is_last_concept and is_last_synonym:
                op = None                    # Final segment — no trailing operator
            elif is_last_synonym:
                op = "AND"                   # Last synonym in group → next group
            else:
                op = "OR"                    # Within group

            pairs.append((synonym, op))

    # Render: each segment is "any,contains,<value>,<OP>" joined by "|"
    segments = []
    for synonym, op in pairs:
        if op:
            segments.append(f"any,contains,{synonym},{op}")
        else:
            segments.append(f"any,contains,{synonym}")

    return "|".join(segments)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — QUERY PRIMO VE API
# ══════════════════════════════════════════════════════════════════════════════

def search_primo(
    query_string: str,
    limit:  int = DEFAULT_LIMIT,
    offset: int = DEFAULT_OFFSET,
    sort:   str = "rank",
    multiFacets: str = "",
) -> dict:
    """
    Sends a GET request to the Primo VE Search API.

    Parameters
    ----------
    query_string : str
        Primo-formatted `q` parameter value (from build_primo_query).
    limit        : int
        Number of results (1–50).
    offset       : int
        Pagination offset.
    sort         : str
        Sort order: "rank" | "date_d" | "date_a" | "title" | "author"
    multiFacets  : str
        Optional facet filters, e.g. "facet_rtype,exact,articles"

    Returns
    -------
    dict  — parsed JSON response from Primo VE, or error dict.
    """
    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n⚠️  WARNING: No API key set.")
        print("   Set PRIMO_API_KEY in your .env file.")
        print("   Get a key at: https://developers.exlibrisgroup.com\n")

    params = {
        "vid"         : VID,
        "tab"         : TAB,
        "scope"       : SCOPE,
        "q"           : query_string,
        "limit"       : limit,
        "offset"      : offset,
        "sort"        : sort,
        "lang"        : "en",
        "apikey"      : API_KEY,
    }

    if multiFacets:
        params["multiFacets"] = multiFacets

    try:
        print(f"\n🔍 Querying Primo VE...")
        print(f"   Endpoint : {BASE_URL}")
        print(f"   VID      : {VID}")
        print(f"   q        : {query_string[:120]}{'...' if len(query_string) > 120 else ''}\n")

        response = requests.get(BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        msg    = e.response.text[:300]   if e.response else str(e)
        return {"error": f"HTTP {status}", "detail": msg}

    except requests.exceptions.ConnectionError:
        return {"error": "Connection failed",
                "detail": "Check network or VPN. CUNY API may require on-campus IP."}

    except requests.exceptions.Timeout:
        return {"error": "Request timed out", "detail": "Try again or reduce query complexity."}

    except Exception as e:
        return {"error": "Unexpected error", "detail": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — FORMAT & DISPLAY RESULTS
# ══════════════════════════════════════════════════════════════════════════════

def format_results(api_response: dict) -> None:
    """
    Pretty-prints Primo VE search results to the console.
    """
    if "error" in api_response:
        print(f"❌ Error: {api_response['error']}")
        print(f"   {api_response.get('detail', '')}")
        return

    # Top-level info
    info = api_response.get("info", {})
    total = info.get("total", 0)
    print(f"✅ Results found : {total}")
    print(f"   Showing       : {info.get('first', 1)}–{info.get('last', DEFAULT_LIMIT)}")
    print("─" * 70)

    docs = api_response.get("docs", [])
    if not docs:
        print("   No records returned.")
        return

    for i, doc in enumerate(docs, 1):
        pnx = doc.get("pnx", {})

        # Title
        display   = pnx.get("display", {})
        title     = display.get("title", ["[No title]"])[0] if display.get("title") else "[No title]"

        # Creator / Author
        creator   = display.get("creator", [""])[0] if display.get("creator") else ""

        # Date
        date      = display.get("creationdate", [""])[0] if display.get("creationdate") else ""

        # Resource type
        rtype     = display.get("type", [""])[0] if display.get("type") else ""

        # Source / Database
        source    = display.get("source", [""])[0] if display.get("source") else ""

        # Brief record ID
        control   = pnx.get("control", {})
        record_id = control.get("recordid", [""])[0] if control.get("recordid") else ""

        # Deep link to Primo VE record
        deep_link = doc.get("delivery", {}).get("GetIt1", [{}])[0].get("links", [{}])[0].get("link", "")

        print(f"  [{i}] {title}")
        if creator : print(f"      Author : {creator}")
        if date    : print(f"      Date   : {date}")
        if rtype   : print(f"      Type   : {rtype}")
        if source  : print(f"      Source : {source}")
        if record_id: print(f"      ID     : {record_id}")
        if deep_link: print(f"      Link   : {deep_link}")
        print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE — phrase → boolean string → API → results
# ══════════════════════════════════════════════════════════════════════════════

def search_from_phrase(
    phrase:  str,
    limit:   int = DEFAULT_LIMIT,
    offset:  int = DEFAULT_OFFSET,
    sort:    str = "rank",
    verbose: bool = True,
) -> dict:
    """
    Full pipeline:
      1. Extract concepts from a natural language phrase
      2. Build a human-readable boolean string
      3. Build a Primo VE API query string
      4. Query the API
      5. Display and return results

    Parameters
    ----------
    phrase  : str   Natural language research phrase
    limit   : int   Results per page (max 50)
    offset  : int   Pagination offset
    sort    : str   "rank" | "date_d" | "date_a" | "title" | "author"
    verbose : bool  Print boolean string and results to console

    Returns
    -------
    dict — raw Primo VE API response
    """
    print("\n" + "═" * 70)
    print(f"  PHRASE   : {phrase}")
    print("═" * 70)

    # Step 1 — Extract concepts
    concepts = extract_concepts(phrase)

    if verbose:
        if concepts:
            print(f"\n📌 Concepts identified: {', '.join(concepts)}")
        else:
            print(f"\n⚠️  No synonym-mapped concepts found. Using raw phrase search.")

    # Step 2 — Human-readable boolean string
    boolean_str = build_boolean_string(concepts) if concepts else f'"{phrase}"'

    if verbose:
        print(f"\n📖 Boolean String:\n")
        print(f"   {boolean_str.replace(chr(10), chr(10) + '   ')}\n")

    # Step 3 — Primo API query string
    primo_query = build_primo_query(concepts, raw_phrase=phrase)

    if verbose:
        print(f"🔧 Primo API q= parameter:\n   {primo_query[:200]}\n")

    # Step 4 — Query the API
    response = search_primo(primo_query, limit=limit, offset=offset, sort=sort)

    # Step 5 — Display results
    if verbose:
        format_results(response)

    return response


def save_results(response: dict, filename: str = "results.json") -> None:
    """Save raw API response to a JSON file for further analysis."""
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(response, f, indent=2, ensure_ascii=False)
    print(f"💾 Results saved to: {filepath}")


# ══════════════════════════════════════════════════════════════════════════════
# EXAMPLE SEARCHES — run directly with: python primo_connector.py
# ══════════════════════════════════════════════════════════════════════════════

EXAMPLE_PHRASES = [
    "interlibrary loan trends in discovery systems at community colleges",
    "Alma analytics resource sharing metrics",
    "access services workflows in academic libraries",
    "copyright fair use course reserves",
]

if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("  BCC / CUNY OneSearch — Primo VE API Connector")
    print("  Bronx Community College Library")
    print("█" * 70)

    # ── Run a single example ─────────────────────────────────────────────────
    phrase = EXAMPLE_PHRASES[0]
    response = search_from_phrase(phrase, limit=5)

    # Optional: save full JSON response to file
    # save_results(response, "search_results.json")

    # ── Uncomment to run all example phrases ─────────────────────────────────
    # for phrase in EXAMPLE_PHRASES:
    #     search_from_phrase(phrase, limit=5)
    #     time.sleep(1)  # Rate limiting: be kind to the API
