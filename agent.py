"""
agent.py
──────────────────────────────────────────────────────────────────────────────
BCC/CUNY Library Search — Agent Pipeline

Architecture
────────────
1. Call Primo VE directly via primo_connector.py  (no SDK needed)
2. Serialize the raw API response into clean record dicts
3. Build the human-readable boolean query string (for the UI badge)
4. Ask the Claude Code CLI (--print mode) to write a natural language
   summary of the results — uses your existing Claude Code session,
   no ANTHROPIC_API_KEY required.

Why not claude_agent_sdk?
────────────────────────
The SDK depends on mcp → jsonschema → jsonschema-specifications, which
reads JSON Schema data files via pathlib at import time.  On macOS with
a pyenv-built Python 3.12, those reads time out (ETIMEDOUT / Errno 60)
due to a macOS filesystem security check on newly installed packages.

This approach sidesteps the entire dependency chain while preserving
the same user-facing behaviour: natural language query → Primo search →
Claude summary → result cards.

Author : Tokunbo Adeshina Jr. — Bronx Community College, CUNY
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from typing import Any

# ── Import existing connector (unchanged) ─────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from primo_connector import (
    search_from_phrase,
    extract_concepts,
    build_boolean_string,
    build_primo_query,
    SYNONYM_MAP,
)


# ══════════════════════════════════════════════════════════════════════════════
# Spell correction  (runs before concept extraction)
# ══════════════════════════════════════════════════════════════════════════════

try:
    from spellchecker import SpellChecker as _SpellChecker
    _spell = _SpellChecker()

    # Teach the checker all known library / domain words so they are never
    # flagged as misspellings.
    _DOMAIN_WORDS: set[str] = set()
    for _key, _syns in SYNONYM_MAP.items():
        for _w in _key.split() + [s for syn in _syns for s in syn.split()]:
            _DOMAIN_WORDS.add(_w.lower())
    _DOMAIN_WORDS.update({
        "primo", "alma", "cuny", "bcc", "bronx", "ebsco", "summon",
        "isbn", "issn", "doi", "oclc", "marc", "rda", "oai", "pmh",
        "metadata", "catalogue", "catalog",
    })
    _spell.word_frequency.load_words(list(_DOMAIN_WORDS))
    _SPELLCHECK_AVAILABLE = True
except ImportError:
    _SPELLCHECK_AVAILABLE = False


def correct_query(phrase: str) -> tuple[str, str | None]:
    """Return (corrected_phrase, correction_note).

    correction_note is None when no changes were made.
    Words are corrected individually; acronyms (ALL-CAPS), very short words
    (≤3 chars), numbers, and domain terms are preserved as-is.
    """
    if not _SPELLCHECK_AVAILABLE or not phrase.strip():
        return phrase, None

    words = phrase.split()
    corrected: list[str] = []
    changed_pairs: list[str] = []

    for word in words:
        # Preserve punctuation attached to the word
        prefix = re.match(r'^([^a-zA-Z]*)', word).group(1)
        suffix = re.search(r'([^a-zA-Z]*)$', word).group(1)
        core   = word[len(prefix):len(word) - len(suffix)] if suffix else word[len(prefix):]

        # Skip: empty, all-caps acronyms, numbers, very short words
        if not core or core.isupper() or core.isdigit() or len(core) <= 3:
            corrected.append(word)
            continue

        fix = _spell.correction(core.lower())
        if fix and fix != core.lower():
            # Preserve original capitalisation style
            if core[0].isupper():
                fix = fix.capitalize()
            corrected.append(prefix + fix + suffix)
            changed_pairs.append(f"{core}→{fix}")
        else:
            corrected.append(word)

    new_phrase = " ".join(corrected)
    note = f"Corrected: {', '.join(changed_pairs)}" if changed_pairs else None
    return new_phrase, note


# ══════════════════════════════════════════════════════════════════════════════
# Claude CLI discovery
# ══════════════════════════════════════════════════════════════════════════════

_CLAUDE_APP_DIR = os.path.expanduser(
    "~/Library/Application Support/Claude/claude-code"
)


def _find_claude_binary() -> str | None:
    """Return the absolute path to the newest installed `claude` binary."""
    if not os.path.isdir(_CLAUDE_APP_DIR):
        return None
    try:
        versions = sorted(os.listdir(_CLAUDE_APP_DIR), reverse=True)
    except OSError:
        return None
    for version in versions:
        candidate = os.path.join(_CLAUDE_APP_DIR, version, "claude")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Result serialiser  (raw Primo JSON → clean dicts for the frontend)
# ══════════════════════════════════════════════════════════════════════════════

# Primo VE base URL for BCC/CUNY permalink construction
_PRIMO_UI_BASE = "https://cuny-bx.primo.exlibrisgroup.com/discovery/fulldisplay"
_PRIMO_VID     = "01CUNY_BX:CUNY_BX"
_PRIMO_SCOPE   = os.getenv("PRIMO_SCOPE", "IZ_CI_AW")
_PRIMO_TAB     = os.getenv("PRIMO_TAB",   "Everything")


def _make_permalink(record_id: str) -> str:
    """Build a correct Primo VE fulldisplay permalink from a record ID.

    Primo VE distinguishes two contexts:
      - context=L   : local IZ/Alma records  (adaptor=Local Search Engine)
      - context=PC  : CDI / PCI central-index records (adaptor=primo_central_multiple_fe)

    CDI record IDs always begin with "cdi_"; everything else is local.
    Including search_scope, adaptor and tab ensures the record opens inside
    the correct discovery context without a "record not found" error.
    """
    if not record_id:
        return ""

    if record_id.startswith("cdi_"):
        context = "PC"
        adaptor = "primo_central_multiple_fe"
    else:
        context = "L"
        adaptor = "Local Search Engine"

    from urllib.parse import quote
    return (
        f"{_PRIMO_UI_BASE}"
        f"?docid={quote(record_id, safe='')}"
        f"&context={context}"
        f"&vid={_PRIMO_VID}"
        f"&lang=en"
        f"&search_scope={_PRIMO_SCOPE}"
        f"&adaptor={quote(adaptor, safe='')}"
        f"&tab={_PRIMO_TAB}"
    )


def serialize_results(raw: dict) -> list[dict]:
    """Convert a raw Primo VE API response into a flat list of record dicts."""
    results: list[dict] = []
    for doc in raw.get("docs", []):
        pnx     = doc.get("pnx", {})
        display = pnx.get("display", {})
        control = pnx.get("control", {})

        def _first(key: str, fallback: str = "") -> str:
            vals = display.get(key) or []
            return vals[0] if vals else fallback

        # Record ID — used to construct the permalink
        record_id = ""
        try:
            record_id = (control.get("recordid") or [])[0]
        except IndexError:
            pass

        # Try the GetIt1 online link first; fall back to constructed permalink.
        # "OVP" is Primo's placeholder for physical-only items — not a real URL.
        link = ""
        try:
            raw_link = doc["delivery"]["GetIt1"][0]["links"][0]["link"]
            is_online = doc["delivery"]["GetIt1"][0]["links"][0].get("isLinktoOnline", False)
            if raw_link and raw_link != "OVP" and is_online:
                link = raw_link
        except (KeyError, IndexError, TypeError):
            pass

        # Always give every record a clickable link
        if not link:
            link = _make_permalink(record_id)

        results.append({
            "title":     _first("title", "[No title]"),
            "creator":   _first("creator"),
            "date":      _first("creationdate"),
            "type":      _first("type"),
            "source":    _first("source"),
            "record_id": record_id,
            "link":      link,
        })
    return results


# ══════════════════════════════════════════════════════════════════════════════
# Claude CLI summary generation
# ══════════════════════════════════════════════════════════════════════════════

def _build_summary_prompt(query: str, results: list[dict], total: int) -> str:
    """Build the prompt we'll send to `claude --print`."""
    lines = [
        "You are a library research assistant at Bronx Community College (BCC), CUNY.",
        f"\nA student searched the BCC/CUNY OneSearch catalog for: {query}",
        f"Total catalog results: {total:,}\n",
        "Top records returned:\n",
    ]
    for i, r in enumerate(results[:5], 1):
        parts = [f"  {i}. {r['title']}"]
        if r["creator"]: parts.append(f"— {r['creator']}")
        if r["date"]:    parts.append(f"({r['date']})")
        if r["type"]:    parts.append(f"[{r['type']}]")
        lines.append(" ".join(parts))

    lines.append(
        "\nWrite a 3–5 sentence summary for the student. "
        "Mention the total number of results, highlight 2–3 of the most "
        "relevant titles by name, and suggest whether to broaden or narrow "
        "the search if appropriate. Keep the tone helpful and professional."
    )
    return "\n".join(lines)


async def _generate_summary(query: str, results: list[dict], total: int) -> str:
    """
    Call `claude --print` as an async subprocess to generate a summary.
    Falls back to a plain-text summary if the CLI is unavailable or times out.
    """
    if not results:
        return (
            f"No results were found for '{query}' in the BCC/CUNY catalog. "
            "Try using broader terms, checking for typos, or searching by "
            "subject rather than exact title."
        )

    binary = _find_claude_binary()
    if not binary:
        return _fallback_summary(query, results, total)

    prompt = _build_summary_prompt(query, results, total)

    # Build a clean env: inherit everything except CLAUDECODE so the subprocess
    # doesn't think it's nested inside a live Claude Code session.
    clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--print",
            "--output-format", "text",
            "--permission-mode", "dontAsk",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=clean_env,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=45)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return _fallback_summary(query, results, total)

        # Strip ANSI escape codes (colour output)
        text = re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", stdout.decode("utf-8", errors="replace")).strip()
        return text if text else _fallback_summary(query, results, total)

    except Exception:
        return _fallback_summary(query, results, total)


def _fallback_summary(query: str, results: list[dict], total: int) -> str:
    """Plain-Python summary used when the Claude CLI is unavailable."""
    if not results:
        return f"No results found for '{query}'. Try broader keywords."
    titles = "; ".join(f'"{r["title"]}"' for r in results[:3])
    return (
        f"Your search for '{query}' returned {total:,} results in the "
        f"BCC/CUNY OneSearch catalog. "
        f"Top matches include: {titles}. "
        "Click any card below to open the full record in the catalog."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point  (called by app.py → POST /search)
# ══════════════════════════════════════════════════════════════════════════════

async def run_search(
    query: str,
    limit: int = 10,
    sort:  str = "rank",
) -> dict:
    """
    Full pipeline:
      1. Build a human-readable boolean string from the query concepts.
      2. Call the Primo VE API via search_from_phrase().
      3. Serialize the raw records.
      4. Generate a natural language summary via the Claude CLI.

    Returns
    ───────
    dict with keys:
        results        : list[dict]  — serialized Primo records
        total          : int         — total hits in the catalog
        boolean_string : str         — human-readable boolean query (for the badge)
        summary        : str         — Claude's (or fallback) natural language summary
        error          : str | None  — set only if the Primo request failed
    """
    # Step 0 — Spell-correct the query before anything else
    corrected_query, correction_note = correct_query(query)

    # Step 1 — Build both query representations
    concepts    = extract_concepts(corrected_query)
    # Human-readable boolean (shown in UI panel, uses synonym expansion)
    boolean_str = build_boolean_string(concepts) if concepts else f'"{corrected_query}"'
    # Actual Primo VE q= parameter (one primary term per concept, AND-joined only)
    primo_query = build_primo_query(concepts, raw_phrase=corrected_query)

    # Step 2 — Search Primo VE
    loop = asyncio.get_event_loop()
    raw  = await loop.run_in_executor(
        None,
        lambda: search_from_phrase(corrected_query, limit=limit, sort=sort, verbose=False),
    )

    if "error" in raw:
        return {
            "results":          [],
            "total":            0,
            "boolean_string":   boolean_str,
            "primo_query":      primo_query,
            "summary":          "",
            "corrected_query":  corrected_query if corrected_query != query else None,
            "correction_note":  correction_note,
            "error":            f"{raw['error']}: {raw.get('detail', '')}",
        }

    # Step 3 — Serialize records
    results = serialize_results(raw)
    total   = raw.get("info", {}).get("total", 0)

    # Step 4 — Generate summary (Claude CLI or fallback)
    summary = await _generate_summary(corrected_query, results, total)

    return {
        "results":          results,
        "total":            total,
        "boolean_string":   boolean_str,
        "primo_query":      primo_query,
        "summary":          summary,
        "corrected_query":  corrected_query if corrected_query != query else None,
        "correction_note":  correction_note,
        "error":            None,
    }
