"""
app.py
──────────────────────────────────────────────────────────────────────────────
BCC/CUNY Library Search — FastAPI Web Application

Serves the single-page search UI and exposes a /search endpoint that runs
the Claude Agent SDK pipeline defined in agent.py.

Endpoints
─────────
  GET  /            → Renders templates/search.html
  POST /search      → Runs the agent pipeline; returns JSON
  GET  /health      → Health check (for monitoring / Power BI bridge parity)

Running
───────
  # Activate your venv first, then:
  python app.py
  # or:
  uvicorn app:app --reload --port 8000

  Open: http://localhost:8000

Author : Tokunbo Adeshina Jr. — Bronx Community College, CUNY
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import sys
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

# ── Import the agent pipeline ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from agent import run_search

# ── App setup ─────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "BCC Library OneSearch Agent",
    description = "Natural language library search powered by Claude Agent SDK + Primo VE",
    version     = "1.0.0",
)

# CORS — allow browser fetch() from localhost during development
app.add_middleware(
    CORSMiddleware,
    allow_origins      = ["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials  = True,
    allow_methods      = ["*"],
    allow_headers      = ["*"],
)

# Jinja2 templates (looks for ./templates/)
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


# ══════════════════════════════════════════════════════════════════════════════
# Request / Response models
# ══════════════════════════════════════════════════════════════════════════════

class SearchRequest(BaseModel):
    """Payload sent by the frontend's fetch() call."""
    query: str = Field(..., min_length=1, description="Natural language research query")
    limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Number of results to return (1–20)",
    )
    sort: Literal["rank", "date_d", "date_a", "title", "author"] = Field(
        default="rank",
        description="Sort order for results",
    )


class RecordModel(BaseModel):
    """One library catalog record returned to the frontend."""
    title:     str
    creator:   str
    date:      str
    type:      str
    source:    str
    record_id: str
    link:      str


class SearchResponse(BaseModel):
    """Full response returned by POST /search."""
    results:        list[RecordModel]
    total:          int
    boolean_string: str
    summary:        str
    error:          Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", include_in_schema=False)
async def index(request: Request):
    """Serve the search UI."""
    return templates.TemplateResponse("search.html", {"request": request})


@app.post("/search", response_model=SearchResponse)
async def search(payload: SearchRequest) -> JSONResponse:
    """
    Run the Claude Agent SDK search pipeline.

    Claude receives the query, calls the `search_library_catalog` MCP tool
    which hits the Primo VE API, then returns a natural language summary
    alongside the structured result records.
    """
    result = await run_search(
        query = payload.query,
        limit = payload.limit,
        sort  = payload.sort,
    )
    return JSONResponse(content=result)


@app.get("/health")
async def health():
    """Health check — mirrors the Alma connector pattern."""
    return {"status": "ok", "service": "BCC Library OneSearch Agent"}


# ══════════════════════════════════════════════════════════════════════════════
# Entrypoint
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "█" * 68)
    print("  BCC Library OneSearch Agent")
    print("  Bronx Community College, CUNY")
    print("█" * 68)
    print(f"  UI     : http://localhost:8000")
    print(f"  API    : http://localhost:8000/search")
    print(f"  Docs   : http://localhost:8000/docs")
    print(f"  Health : http://localhost:8000/health")
    print("█" * 68 + "\n")

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
