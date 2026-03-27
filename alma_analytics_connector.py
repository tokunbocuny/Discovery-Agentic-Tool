"""
alma_analytics_connector.py
──────────────────────────────────────────────────────────────────────────────
Bronx Community College – Alma Analytics → Power BI Connector

Fetches reports from the Ex Libris Alma Analytics REST API, handles
resumption-token pagination, parses the ROWSET XML, and exports data to
CSV, Excel, or JSON for import into Microsoft Power BI.

Also runs as a lightweight local REST server (FastAPI) so Power BI can
connect live via the built-in Web connector.

Author      : Tokunbo Adeshina Jr.
Institution : Bronx Community College, CUNY
API Docs    : https://developers.exlibrisgroup.com/alma/apis/analytics/

SETUP:
  1. Add ALMA_API_KEY (and optionally ALMA_BASE_URL) to your .env file.
  2. pip install requests python-dotenv pandas openpyxl
     # For server mode also: pip install fastapi uvicorn
  3a. Export mode  : python alma_analytics_connector.py \\
                       --path "/shared/BCC/Reports/Acquisitions/FY2025" \\
                       --format excel
  3b. Server mode  : python alma_analytics_connector.py --serve
  3c. Power Query  : python alma_analytics_connector.py --powerquery
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────────
BASE_URL      = os.getenv(
    "ALMA_BASE_URL",
    "https://api-na.hosted.exlibrisgroup.com/almaws/v1/analytics/reports",
)
API_KEY       = os.getenv("ALMA_API_KEY", "YOUR_ALMA_API_KEY_HERE")
DEFAULT_LIMIT = int(os.getenv("ALMA_ROW_LIMIT", "1000"))  # API max: 1000

# Namespace prefix used by Alma for human-readable column headings
SAW_SQL_NS = "com.siebel.analytics.web/report/v1.1"
ROWSET_NS  = "urn:schemas-microsoft-com:xml-analysis:rowset"


# ══════════════════════════════════════════════════════════════════════════════
# ALMA ANALYTICS CLIENT
# ══════════════════════════════════════════════════════════════════════════════

class AlmaAnalyticsClient:
    """
    Thin wrapper around the Alma Analytics REST API.

    Handles:
    - Single-page and paginated (resumption-token) fetches
    - ROWSET XML parsing with human-readable column name extraction
    - DataFrame construction
    """

    def __init__(
        self,
        api_key:  str = API_KEY,
        base_url: str = BASE_URL,
    ) -> None:
        self.api_key  = api_key
        self.base_url = base_url
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/xml"})

    # ── Private: fetch one page ───────────────────────────────────────────────
    def _fetch_page(
        self,
        path:      str,
        limit:     int            = DEFAULT_LIMIT,
        token:     Optional[str]  = None,
        col_names: bool           = True,
    ) -> dict:
        """
        Call the Alma Analytics endpoint for a single page of results.

        Returns a dict:
            rows         – list[dict]  parsed data rows
            token        – str | None  resumption token for next page
            is_finished  – bool
            col_map      – dict[str, str]  internal tag → human heading
        """
        params: dict = {
            "path":      path,
            "limit":     limit,
            "col_names": "true" if col_names else "false",
            "apikey":    self.api_key,
        }
        if token:
            params["token"] = token

        try:
            resp = self._session.get(self.base_url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else "?"
            body   = exc.response.text[:600]  if exc.response else str(exc)
            raise RuntimeError(f"HTTP {status}: {body}") from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Request failed: {exc}") from exc

        return self._parse_xml(resp.text)

    # ── Private: XML parser ───────────────────────────────────────────────────
    def _parse_xml(self, xml_text: str) -> dict:
        """
        Parse one Alma Analytics XML response envelope.

        Response skeleton:
            <report>
              <QueryResult>
                <ResumptionToken>…</ResumptionToken>
                <IsFinished>true|false</IsFinished>
                <ResultXml>
                  <rowset xmlns="urn:schemas-microsoft-com:xml-analysis:rowset"
                          xmlns:xsd="…" xmlns:xsi="…">
                    <xsd:schema>
                      <xsd:element name="Row">
                        <xsd:complexType><xsd:sequence>
                          <xsd:element name="Column0" type="xsd:string"
                                       saw-sql:columnHeading="My Column"/>
                          …
                        </xsd:sequence></xsd:complexType>
                      </xsd:element>
                    </xsd:schema>
                    <Row><Column0>val</Column0>…</Row>
                    …
                  </rowset>
                </ResultXml>
              </QueryResult>
            </report>
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise RuntimeError(
                f"XML parse error: {exc}\nRaw snippet:\n{xml_text[:400]}"
            ) from exc

        def first_text(tag: str) -> Optional[str]:
            """Find first element by local tag name (namespace-agnostic)."""
            for el in root.iter():
                local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
                if local == tag:
                    return (el.text or "").strip() or None
            return None

        # ── Pagination controls ───────────────────────────────────────────────
        raw_token   = first_text("ResumptionToken")
        raw_finish  = first_text("IsFinished") or "true"
        is_finished = raw_finish.lower() == "true"
        token       = raw_token if not is_finished else None

        # ── Column mapping: internal XML tag → human heading ─────────────────
        # The XSD schema lives inside <xsd:schema> (namespace-qualified).
        # Each column element carries a  saw-sql:columnHeading  attribute.
        col_map: dict[str, str] = {}
        saw_attr = f"{{{SAW_SQL_NS}}}columnHeading"
        xsd_ns   = "http://www.w3.org/2001/XMLSchema"

        for el in root.iter():
            local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            # We want <xsd:element> nodes that have a "name" attr and are NOT
            # the top-level "Row" wrapper.
            if local == "element":
                col_name = el.get("name", "")
                heading  = el.get(saw_attr, "") or el.get("columnHeading", "")
                if col_name and col_name != "Row":
                    col_map[col_name] = heading if heading else col_name

        # ── Data rows ─────────────────────────────────────────────────────────
        rows: list[dict] = []
        for row_el in root.iter("Row"):
            row: dict[str, str] = {}
            for child in row_el:
                raw_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                # Use human heading when available, fall back to tag name
                key      = col_map.get(raw_tag, raw_tag)
                row[key] = child.text or ""
            if row:
                rows.append(row)

        return {
            "rows":        rows,
            "token":       token,
            "is_finished": is_finished,
            "col_map":     col_map,
        }

    # ── Public: paginated fetch → DataFrame ──────────────────────────────────
    def fetch_all(
        self,
        path:     str,
        limit:    int  = DEFAULT_LIMIT,
        max_rows: int  = 0,
        verbose:  bool = True,
    ) -> pd.DataFrame:
        """
        Fetch ALL rows for an Analytics report, handling pagination automatically.

        Parameters
        ----------
        path     : Full Alma Analytics report path
                   e.g. "/shared/BCC/Reports/Acquisitions/FY2025"
        limit    : Rows per API request (max 1000).
        max_rows : Stop after this many total rows (0 = unlimited).
        verbose  : Print progress to stdout.

        Returns
        -------
        pd.DataFrame with one column per report field.
        """
        if self.api_key == "YOUR_ALMA_API_KEY_HERE":
            print("\n  WARNING: No ALMA_API_KEY found in .env")
            print("  Register at https://developers.exlibrisgroup.com\n")

        all_rows: list[dict] = []
        token:    Optional[str] = None
        page:     int = 0

        if verbose:
            print(f"\nFetching : {path}")
            print(f"Limit    : {limit} rows/request")

        while True:
            page += 1
            if verbose:
                print(f"  page {page:>3}  |  rows so far: {len(all_rows):>6}", end="\r")

            result = self._fetch_page(
                path,
                limit=limit,
                token=token,
                col_names=(page == 1),
            )
            all_rows.extend(result["rows"])

            if result["is_finished"] or not result["token"]:
                break

            token = result["token"]

            if max_rows and len(all_rows) >= max_rows:
                all_rows = all_rows[:max_rows]
                break

        if verbose:
            print(f"\nDone.    Total rows: {len(all_rows):,}")

        return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def export_csv(df: pd.DataFrame, out_path: str = "alma_report.csv") -> str:
    df.to_csv(out_path, index=False)
    print(f"  Saved → {out_path}")
    return out_path


def export_excel(
    df:         pd.DataFrame,
    out_path:   str = "alma_report.xlsx",
    sheet_name: str = "Alma Analytics",
) -> str:
    df.to_excel(out_path, index=False, sheet_name=sheet_name)
    print(f"  Saved → {out_path}")
    return out_path


def export_json(df: pd.DataFrame, out_path: str = "alma_report.json") -> str:
    df.to_json(out_path, orient="records", indent=2)
    print(f"  Saved → {out_path}")
    return out_path


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL API SERVER  —  for live Power BI Web connector
# ══════════════════════════════════════════════════════════════════════════════

def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """
    Starts a FastAPI server that proxies Alma Analytics data as JSON.

    Power BI Web connector URL:
        http://127.0.0.1:8765/report?path=/shared/BCC/Reports/MyReport

    Power BI steps:
        Home → Get Data → Web → Basic
        URL : http://127.0.0.1:8765/report?path=/shared/…/MyReport
        Power BI will auto-detect the JSON list and turn it into a table.
    """
    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.responses import JSONResponse, PlainTextResponse
        import uvicorn
    except ImportError:
        print(
            "\nERROR: server mode requires fastapi and uvicorn.\n"
            "  pip install fastapi uvicorn\n"
        )
        sys.exit(1)

    client = AlmaAnalyticsClient()

    app = FastAPI(
        title="Alma Analytics → Power BI Bridge",
        version="1.0.0",
        description=(
            "Local bridge that proxies Ex Libris Alma Analytics reports "
            "as JSON or CSV for Microsoft Power BI."
        ),
    )

    @app.get("/health", summary="Health check")
    def health():
        return {"status": "ok", "service": "Alma Analytics Bridge"}

    @app.get(
        "/report",
        summary="Fetch an Alma Analytics report",
        description=(
            "**Power BI usage:** Get Data → Web → Basic → "
            f"http://{host}:{port}/report?path=/shared/BCC/Reports/MyReport"
        ),
    )
    def get_report(
        path:     str = Query(...,           description="Full Alma Analytics report path"),
        limit:    int = Query(DEFAULT_LIMIT, description="Rows per API page (max 1000)", ge=1, le=1000),
        max_rows: int = Query(0,             description="Cap on total rows (0 = unlimited)", ge=0),
        format:   str = Query("json",        description="Response format: json | csv"),
    ):
        try:
            df = client.fetch_all(
                path=path, limit=limit, max_rows=max_rows, verbose=False
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        if df.empty:
            if format == "csv":
                return PlainTextResponse("", media_type="text/csv")
            return JSONResponse(content=[], status_code=200)

        if format == "csv":
            return PlainTextResponse(
                content=df.to_csv(index=False), media_type="text/csv"
            )

        return JSONResponse(
            content=json.loads(df.to_json(orient="records"))
        )

    print("\n" + "═" * 68)
    print("  Alma Analytics → Power BI Bridge")
    print("  Bronx Community College Library, CUNY")
    print("═" * 68)
    print(f"  Listening : http://{host}:{port}")
    print(f"  Health    : http://{host}:{port}/health")
    print(f"  Docs      : http://{host}:{port}/docs")
    print()
    print("  Power BI Web connector URL (replace report path):")
    print(f"    http://{host}:{port}/report?path=/shared/BCC/Reports/MyReport")
    print()
    print("  Steps in Power BI Desktop:")
    print("    Home → Get Data → Web → Basic → paste URL above → OK")
    print("    Power Query will detect the JSON list as a table automatically.")
    print("═" * 68 + "\n")

    uvicorn.run(app, host=host, port=port, log_level="warning")


# ══════════════════════════════════════════════════════════════════════════════
# POWER QUERY M TEMPLATE
# Print with: python alma_analytics_connector.py --powerquery
# ══════════════════════════════════════════════════════════════════════════════

POWER_QUERY_M = '''\
// ─────────────────────────────────────────────────────────────────────────────
//  Alma Analytics → Power BI  |  Power Query M  (Advanced Editor template)
//  Institution : Bronx Community College, CUNY
//
//  Usage in Power BI Desktop:
//    Home → Transform Data → Advanced Editor → paste this → Done
// ─────────────────────────────────────────────────────────────────────────────
let
    // ── EDIT THESE TWO VALUES ────────────────────────────────────────────────
    AlmaApiKey  = "YOUR_ALMA_API_KEY_HERE",
    ReportPath  = "/shared/BCC/Reports/Acquisitions/FY2025",
    // ────────────────────────────────────────────────────────────────────────

    BaseUrl    = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/analytics/reports",
    RowLimit   = "1000",
    SawSqlNs   = "com.siebel.analytics.web/report/v1.1",

    // Recursive helper: fetch one page, return {rows, nextToken, done}
    FetchPage = (resumptionToken as nullable text) as record =>
        let
            Params0 = [path = ReportPath, limit = RowLimit,
                       col_names = "true", apikey = AlmaApiKey],
            Params  = if resumptionToken = null then Params0
                      else Record.AddField(Params0, "token", resumptionToken),
            Url     = BaseUrl & "?" & Uri.BuildQueryString(Params),
            Raw     = Web.Contents(Url, [Headers = [Accept = "application/xml"]]),
            Doc     = Xml.Document(Raw),

            // Navigate into QueryResult
            QR      = Doc{[Name = "report"]}[Value]{[Name = "QueryResult"]}[Value],

            IsDoneText = try QR{[Name = "IsFinished"]}[Value]{0}[Value]
                         otherwise "true",
            IsDone  = Text.Lower(IsDoneText) = "true",

            NextTok = try QR{[Name = "ResumptionToken"]}[Value]{0}[Value]
                      otherwise null,

            // Navigate into ResultXml → rowset → Row elements
            RowsetTable = QR{[Name = "ResultXml"]}[Value]{0}[Value],
            Rows        = try RowsetTable{[Name = "Row"]}[Value]
                          otherwise {},

            // Each Row is a record with field names = XML tag names
            RowList = List.Transform(
                          Rows,
                          each Record.FromTable(
                                   Table.RenameColumns(
                                       Table.SelectColumns(_, {"Name","Value"}),
                                       {{"Value","v"}}
                                   )
                               )
                      )
        in
            [rows = RowList,
             nextToken = if IsDone then null else NextTok,
             done = IsDone],

    // Collect all pages via List.Generate
    AllPages = List.Generate(
        ()    => FetchPage(null),
        each  not (_[done] and List.Count(_[rows]) = 0),
        each  if _[done]
              then [rows = {}, nextToken = null, done = true]
              else FetchPage(_[nextToken]),
        each  _[rows]
    ),

    AllRows = List.Combine(AllPages),
    Result  = Table.FromRecords(AllRows)
in
    Result
'''


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="alma_analytics_connector",
        description="Alma Analytics → Power BI Connector  |  BCC/CUNY",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
────────
  Export to Excel (default):
    python alma_analytics_connector.py \\
      --path "/shared/BCC/Reports/Acquisitions/FY2025"

  Export to CSV with custom filename:
    python alma_analytics_connector.py \\
      --path "/shared/BCC/Reports/Circulation/Monthly" \\
      --format csv --output circ_monthly.csv

  Export to JSON:
    python alma_analytics_connector.py \\
      --path "/shared/BCC/Reports/ILL/Summary" \\
      --format json

  Start live server for Power BI Web connector:
    python alma_analytics_connector.py --serve

  Print Power Query M template for Power BI Advanced Editor:
    python alma_analytics_connector.py --powerquery
""",
    )

    parser.add_argument(
        "--path",
        type=str,
        default="",
        help='Full Alma Analytics report path  e.g. "/shared/BCC/Reports/…"',
    )
    parser.add_argument(
        "--format",
        choices=["excel", "csv", "json"],
        default="excel",
        help="Export format (default: excel)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output filename  (auto-generated from report name if omitted)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Rows per API request, max 1000 (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=0,
        dest="max_rows",
        help="Cap total rows fetched  (0 = no cap)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start local REST server so Power BI can connect live",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for --serve mode (default: 8765)",
    )
    parser.add_argument(
        "--powerquery",
        action="store_true",
        help="Print the Power Query M template for Power BI Advanced Editor",
    )

    args = parser.parse_args()

    print("\n" + "█" * 68)
    print("  Alma Analytics → Power BI Connector")
    print("  Bronx Community College Library, CUNY")
    print("█" * 68)

    # ── Power Query template mode ──────────────────────────────────────────
    if args.powerquery:
        print("\nPower Query M Template")
        print("Paste into Power BI Desktop → Home → Transform Data → Advanced Editor")
        print("─" * 68)
        print(POWER_QUERY_M)
        return

    # ── Server mode ────────────────────────────────────────────────────────
    if args.serve:
        run_server(port=args.port)
        return

    # ── Export mode ────────────────────────────────────────────────────────
    if not args.path:
        parser.error(
            "--path is required for export mode.\n"
            "Use --serve for the live server or --powerquery for the M template."
        )

    client = AlmaAnalyticsClient()
    df = client.fetch_all(
        path=args.path,
        limit=args.limit,
        max_rows=args.max_rows,
        verbose=True,
    )

    if df.empty:
        print(
            "\nNo rows returned.\n"
            "Check: 1) report path is correct  2) ALMA_API_KEY in .env  "
            "3) API key has 'Analytics' read permission"
        )
        return

    print(f"\nShape   : {df.shape[0]:,} rows × {df.shape[1]} columns")
    cols_preview = ", ".join(df.columns[:6].tolist())
    if df.shape[1] > 6:
        cols_preview += " …"
    print(f"Columns : {cols_preview}")

    # Auto-generate output filename from report path stem
    ext_map   = {"excel": ".xlsx", "csv": ".csv", "json": ".json"}
    stem      = Path(args.path).stem if args.path else "alma_report"
    out_file  = args.output or f"{stem}{ext_map[args.format]}"

    print()
    if   args.format == "excel": export_excel(df, out_file)
    elif args.format == "csv":   export_csv(df, out_file)
    elif args.format == "json":  export_json(df, out_file)

    print()
    print("Power BI import steps:")
    if args.format == "excel":
        print("  Home → Get Data → Excel Workbook → select file → Load")
    elif args.format == "csv":
        print("  Home → Get Data → Text/CSV → select file → Load")
    elif args.format == "json":
        print("  Home → Get Data → JSON → select file → Load")


if __name__ == "__main__":
    main()
