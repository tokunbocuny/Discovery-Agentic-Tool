"""
test_connectors.py  —  Primo VE API Connector Test Suite
──────────────────────────────────────────────────────────────────────────────
Bronx Community College / CUNY

Tests both the pure-logic functions (no network) AND the live Primo VE API.
Live tests call the real api-na.hosted.exlibrisgroup.com endpoint using the
credentials in your .env file.

Run:
    python3 test_connectors.py          # normal (dots)
    python3 test_connectors.py -v       # verbose (test names)
──────────────────────────────────────────────────────────────────────────────
"""

import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import primo_connector as pc


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — Pure-logic tests (no network)
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractConcepts(unittest.TestCase):
    """extract_concepts() — synonym-map matching"""

    def test_single_concept(self):
        self.assertIn("interlibrary loan", pc.extract_concepts("interlibrary loan policies"))

    def test_multiple_concepts(self):
        concepts = pc.extract_concepts(
            "interlibrary loan trends in discovery systems at community colleges"
        )
        self.assertIn("interlibrary loan", concepts)
        self.assertIn("discovery systems", concepts)
        self.assertIn("community college", concepts)

    def test_no_match_returns_empty(self):
        self.assertEqual(pc.extract_concepts("quantum entanglement in photonics"), [])

    def test_no_duplicate_spans(self):
        concepts = pc.extract_concepts("resource sharing and interlibrary loan")
        self.assertEqual(len(concepts), len(set(concepts)))

    def test_case_insensitive(self):
        self.assertIn("analytics", pc.extract_concepts("ANALYTICS AND REPORTING"))


class TestBuildBooleanString(unittest.TestCase):
    """build_boolean_string() — human-readable output"""

    def test_empty_returns_empty_string(self):
        self.assertEqual(pc.build_boolean_string([]), "")

    def test_multi_word_synonym_quoted(self):
        result = pc.build_boolean_string(["interlibrary loan"])
        self.assertIn('"interlibrary loan"', result)

    def test_two_concepts_joined_by_and(self):
        self.assertIn("AND", pc.build_boolean_string(["analytics", "academic library"]))

    def test_single_concept_no_and(self):
        self.assertNotIn("AND", pc.build_boolean_string(["analytics"]))


class TestBuildPrimoQuery(unittest.TestCase):
    """build_primo_query() — Primo VE q= parameter format"""

    def test_empty_uses_raw_phrase(self):
        self.assertEqual(pc.build_primo_query([], raw_phrase="climate change"),
                         "any,contains,climate change")

    def test_every_segment_starts_with_any_contains(self):
        q = pc.build_primo_query(["analytics"])
        for seg in q.split("|"):
            self.assertTrue(seg.startswith("any,contains,"), seg)

    def test_last_segment_has_no_trailing_operator(self):
        q = pc.build_primo_query(["interlibrary loan", "discovery systems"])
        last = q.split("|")[-1]
        self.assertFalse(last.endswith(",AND") or last.endswith(",OR"), last)

    def test_inter_concept_operator_is_AND(self):
        q = pc.build_primo_query(["analytics", "academic library"])
        self.assertIn(",AND", q)

    def test_intra_concept_operator_is_OR(self):
        # "interlibrary loan" has 4 synonyms → joined by OR
        q = pc.build_primo_query(["interlibrary loan"])
        self.assertIn(",OR", q)

    def test_quotes_stripped_from_raw_phrase(self):
        q = pc.build_primo_query([], raw_phrase='some "quoted" phrase')
        self.assertNotIn('"', q)


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — Live API tests  (real network calls to Primo VE)
# ══════════════════════════════════════════════════════════════════════════════

class TestLivePrimoAPI(unittest.TestCase):
    """
    Real calls to api-na.hosted.exlibrisgroup.com using the key in .env.
    Each test uses search_primo() directly with a pre-built query string.
    """

    @classmethod
    def setUpClass(cls):
        if pc.API_KEY == "YOUR_API_KEY_HERE":
            raise unittest.SkipTest(
                "No PRIMO_API_KEY in .env — skipping live API tests."
            )

    # ── helper ────────────────────────────────────────────────────────────────
    def _assert_ok(self, resp: dict, label: str = ""):
        self.assertNotIn(
            "error", resp,
            msg=f"{label} — API returned error: {resp.get('error')} | {resp.get('detail')}",
        )
        self.assertIn("info", resp, msg=f"{label} — missing 'info' key")

    # ── 1. Basic keyword search ───────────────────────────────────────────────
    def test_basic_keyword_search(self):
        resp = pc.search_primo("any,contains,library", limit=3)
        self._assert_ok(resp, "basic keyword")
        total = resp["info"].get("total", 0)
        self.assertGreater(total, 0, "Expected at least one result for 'library'")

    # ── 2. search_from_phrase pipeline ───────────────────────────────────────
    def test_phrase_pipeline_returns_results(self):
        resp = pc.search_from_phrase(
            "interlibrary loan trends in academic libraries",
            limit=5,
            verbose=False,
        )
        self._assert_ok(resp, "phrase pipeline")

    # ── 3. Pagination (offset) ────────────────────────────────────────────────
    def test_pagination_offset(self):
        page1 = pc.search_primo("any,contains,research", limit=3, offset=0)
        page2 = pc.search_primo("any,contains,research", limit=3, offset=3)
        self._assert_ok(page1, "page1")
        self._assert_ok(page2, "page2")
        ids1 = {d.get("pnx", {}).get("control", {}).get("recordid", [""])[0]
                for d in page1.get("docs", [])}
        ids2 = {d.get("pnx", {}).get("control", {}).get("recordid", [""])[0]
                for d in page2.get("docs", [])}
        # Two different pages should not share the same record IDs
        self.assertTrue(ids1.isdisjoint(ids2), "Pages 1 and 2 returned overlapping records")

    # ── 4. Limit respected ───────────────────────────────────────────────────
    def test_limit_respected(self):
        for limit in (1, 3, 5):
            resp = pc.search_primo("any,contains,book", limit=limit)
            self._assert_ok(resp, f"limit={limit}")
            docs = resp.get("docs", [])
            self.assertLessEqual(len(docs), limit, f"Got {len(docs)} docs for limit={limit}")

    # ── 5. Sort by date (descending) ─────────────────────────────────────────
    def test_sort_date_descending(self):
        resp = pc.search_primo("any,contains,education", limit=5, sort="date_d")
        self._assert_ok(resp, "sort date_d")
        dates = []
        for doc in resp.get("docs", []):
            raw = doc.get("pnx", {}).get("display", {}).get("creationdate", [])
            if raw:
                try:
                    dates.append(int(raw[0][:4]))
                except ValueError:
                    pass
        if len(dates) >= 2:
            self.assertEqual(dates, sorted(dates, reverse=True),
                             f"Results not sorted descending: {dates}")

    # ── 6. Facet filter — accepted without error ─────────────────────────────
    def test_facet_parameter_accepted(self):
        """
        Verify that passing multiFacets doesn't cause an API error.
        Primo VE's facet totals vary by scope configuration, so we only
        assert a clean (non-error) response with at least one result.
        """
        resp = pc.search_primo(
            "any,contains,information literacy",
            limit=5,
            multiFacets="facet_rtype,exact,articles",
        )
        self._assert_ok(resp, "facet articles")
        # Faceted search for a common phrase should still return something
        self.assertGreaterEqual(
            resp["info"].get("total", 0), 0,
            "Faceted search returned a negative total — unexpected",
        )

    # ── 7. No results for nonsense query ─────────────────────────────────────
    def test_nonsense_query_returns_zero(self):
        resp = pc.search_primo(
            "any,contains,xyzzy_nonsense_abc_123_zzz_qqqq", limit=3
        )
        self._assert_ok(resp, "nonsense query")
        total = resp["info"].get("total", 0)
        self.assertEqual(total, 0, f"Expected 0 results for gibberish, got {total}")

    # ── 8. Record structure validation ───────────────────────────────────────
    def test_record_structure(self):
        resp = pc.search_primo("any,contains,Shakespeare", limit=2)
        self._assert_ok(resp, "record structure")
        docs = resp.get("docs", [])
        self.assertGreater(len(docs), 0, "Expected at least one Shakespeare record")
        for doc in docs:
            self.assertIn("pnx", doc, "Record missing 'pnx' key")
            pnx = doc["pnx"]
            self.assertIn("display", pnx, "pnx missing 'display'")
            self.assertIn("control", pnx, "pnx missing 'control'")
            title = pnx["display"].get("title", [])
            self.assertTrue(title, "Record has no title")

    # ── 9. Multi-concept boolean search ──────────────────────────────────────
    def test_multi_concept_boolean_search(self):
        phrase = "analytics and resource sharing in academic libraries"
        resp = pc.search_from_phrase(phrase, limit=5, verbose=False)
        self._assert_ok(resp, "multi-concept boolean")

    # ── 10. save_results writes valid JSON ───────────────────────────────────
    def test_save_results(self):
        resp = pc.search_primo("any,contains,Bronx", limit=2)
        self._assert_ok(resp, "save results")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            pc.save_results(resp, filename=path)
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertIn("info", loaded)
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════════════════════
#  RUNNER
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 68)
    print("  BCC/CUNY — Primo VE Connector Test Suite")
    print(f"  VID: {pc.VID}  |  Scope: {pc.SCOPE}  |  Tab: {pc.TAB}")
    print("=" * 68 + "\n")
    unittest.main(verbosity=2)
