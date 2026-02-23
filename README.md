# Boolean Search String Builder

A reference guide for breaking down natural language phrases into structured boolean search strings for library databases, research platforms, and information retrieval systems.

---

## Table of Contents

- [What Are Boolean Operators?](#what-are-boolean-operators)
- [Core Operators](#core-operators)
- [Phrase-to-Boolean Breakdown Method](#phrase-to-boolean-breakdown-method)
- [Step-by-Step Examples](#step-by-step-examples)
- [Advanced Techniques](#advanced-techniques)
- [Database-Specific Notes](#database-specific-notes)
- [Quick Reference Cheat Sheet](#quick-reference-cheat-sheet)

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
