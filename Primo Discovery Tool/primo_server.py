"""
primo_server.py
────────────────────────────────────────────────────────────────────────────
Local HTTP server for the Primo Discovery Tool HTML front-end.

Reads API credentials from ../.env (or the directory .env), serves the HTML
file, and proxies search requests to the Primo VE API so the browser never
needs to hold an API key.

Usage:
    python primo_server.py          # starts on http://localhost:8766
    python primo_server.py --port 9000

Then open http://localhost:8766 in your browser.
────────────────────────────────────────────────────────────────────────────
"""

import argparse
import json
import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────────────────
# Look in this file's directory first, then one level up (project root)
_here = Path(__file__).parent
for _env_path in [_here / ".env", _here.parent / ".env"]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

API_KEY  = os.getenv("PRIMO_API_KEY", "")
VID      = os.getenv("PRIMO_VID",     "01CUNY_BX:CUNY_BX")
SCOPE    = os.getenv("PRIMO_SCOPE",   "IZ_CI_AW")
TAB      = os.getenv("PRIMO_TAB",     "Everything")
BASE_URL = os.getenv("PRIMO_BASE_URL",
                     "https://api-na.hosted.exlibrisgroup.com/primo/v1/search")

HTML_FILE = _here / "primo_discovery_tool.html"


# ── Request handler ──────────────────────────────────────────────────────────
class PrimoHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} → {fmt % args}")

    # ── GET ──────────────────────────────────────────────────────────────────
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._serve_html()
        elif path == "/api/search":
            self._proxy_search(parsed.query)
        elif path == "/api/config":
            self._serve_config()
        else:
            self._respond(404, "text/plain", b"Not found")

    # ── Serve the HTML file ──────────────────────────────────────────────────
    def _serve_html(self):
        if not HTML_FILE.exists():
            self._respond(404, "text/plain",
                          b"primo_discovery_tool.html not found in this directory.")
            return
        self._respond(200, "text/html; charset=utf-8", HTML_FILE.read_bytes())

    # ── Expose non-secret config to the front-end ────────────────────────────
    def _serve_config(self):
        payload = json.dumps({
            "vid":   VID,
            "scope": SCOPE,
            "tab":   TAB,
            "configured": bool(API_KEY),
        }).encode()
        self._respond(200, "application/json", payload)

    # ── Proxy search to Primo VE API ─────────────────────────────────────────
    def _proxy_search(self, query_string):
        if not API_KEY:
            err = json.dumps({"error": "No API key configured.",
                              "detail": "Set PRIMO_API_KEY in your .env file."}).encode()
            self._respond(503, "application/json", err)
            return

        params_in = urllib.parse.parse_qs(query_string, keep_blank_values=False)

        def first(key, default=""):
            return params_in.get(key, [default])[0]

        params = {
            "vid":    VID,
            "tab":    TAB,
            "scope":  SCOPE,
            "q":      first("q"),
            "limit":  first("limit", "5"),
            "offset": first("offset", "0"),
            "sort":   first("sort", "rank"),
            "lang":   "en",
            "apikey": API_KEY,
        }

        facets = first("multiFacets")
        if facets:
            params["multiFacets"] = facets

        try:
            resp = requests.get(BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            self._respond(200, "application/json", resp.content)
        except requests.exceptions.HTTPError as e:
            status  = e.response.status_code if e.response else 502
            detail  = e.response.text[:400]  if e.response else str(e)
            payload = json.dumps({"error": f"HTTP {status}", "detail": detail}).encode()
            self._respond(status, "application/json", payload)
        except requests.exceptions.ConnectionError:
            payload = json.dumps({
                "error": "Connection failed",
                "detail": "Cannot reach the Ex Libris API. Check network/VPN."
            }).encode()
            self._respond(502, "application/json", payload)
        except requests.exceptions.Timeout:
            payload = json.dumps({
                "error": "Request timed out",
                "detail": "The Primo API did not respond within 15 seconds."
            }).encode()
            self._respond(504, "application/json", payload)

    # ── Low-level response helper ─────────────────────────────────────────────
    def _respond(self, status, content_type, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ── Entry point ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Primo Discovery Tool local server")
    parser.add_argument("--port", type=int, default=8766,
                        help="Port to listen on (default: 8766)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not open the browser automatically")
    args = parser.parse_args()

    if not API_KEY:
        print("\n⚠️  WARNING: PRIMO_API_KEY is not set in .env")
        print("   Steps 1–3 (concept extraction, boolean string) will still work.")
        print("   Steps 4–5 (live API results) require a valid key.\n")
    else:
        print(f"\n✅ Loaded API key from .env  (VID: {VID}, Scope: {SCOPE}, Tab: {TAB})")

    url = f"http://localhost:{args.port}"
    print(f"🚀 Starting server at {url}")
    print("   Press Ctrl+C to stop.\n")

    if not args.no_browser:
        webbrowser.open(url)

    server = HTTPServer(("localhost", args.port), PrimoHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")


if __name__ == "__main__":
    main()
