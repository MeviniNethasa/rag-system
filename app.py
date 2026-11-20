"""Web UI for the spare-parts lookup.

    uvicorn app:app --reload --port 8000

GET  /            -> static/index.html (search box + diagram with highlights)
POST /api/search  -> {"query": "..."} -> matched parts (exact stored casing)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from parts_rag import llm, retriever  # noqa: E402
from parts_rag.query_router import find_part_codes  # noqa: E402

STATIC_DIR = ROOT / "static"
ASSEMBLY_LABEL = "28. Front Wheel Assembly - Disc Brake"

log = logging.getLogger("parts_rag.app")

app = FastAPI(title="Spare Parts Lookup", docs_url="/api/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=200)


class Part(BaseModel):
    sr_no: int
    part_no: str
    description: str
    qty: int


class SearchResponse(BaseModel):
    found: bool
    query: str
    route: str              # part_no | sr_no | description
    mode: str               # exact | ci_fallback | none | sr_no | keyword | vector
    message: str = ""
    answer: str | None = None
    parts: list[Part] = []


def _part(hit: retriever.Hit) -> Part:
    m = hit.metadata
    return Part(sr_no=int(m["sr_no"]), part_no=m["part_no"],
                description=m["description"], qty=int(m["qty"]))


def _ground_with_claude(result: retriever.Result) -> tuple[list[retriever.Hit], str | None, str]:
    """Vector hits are candidates, not matches: keep only the parts Claude
    names. If Claude is unavailable, fall back to the single closest row."""
    import anthropic

    try:
        ans = llm.answer(result)
    except (anthropic.APIError, RuntimeError) as e:  # RuntimeError: missing API key
        log.warning("Claude call failed (%s); using closest vector match", type(e).__name__)
        return result.rows[:1], None, "Showing the closest match (AI answer unavailable)."
    named = set(find_part_codes(ans.text))
    rows = [h for h in result.rows if h.metadata["part_no"] in named]
    return rows, ans.text, ""


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    query = req.query.strip()
    if not query:
        return SearchResponse(found=False, query="", route="", mode="",
                              message="Type a part number, diagram number or description.")
    try:
        result = retriever.retrieve(query)
    except Exception:
        log.exception("retrieve failed for %r", query)
        raise HTTPException(status_code=502, detail="Search backend is unavailable. Try again shortly.")

    rows, answer, message = result.rows, None, ""
    if result.lookup_mode == "vector" and rows:
        rows, answer, message = _ground_with_claude(result)

    parts = [_part(h) for h in rows]
    if not parts:
        message = message or (result.notes[0] if result.notes else "")
        message = message or f"No part matched “{query}” in {ASSEMBLY_LABEL}."
    elif result.lookup_mode == "ci_fallback":
        message = f"No exact match for that casing; showing the stored Part No. {parts[0].part_no}."

    return SearchResponse(
        found=bool(parts),
        query=query,
        route=result.route.mode,
        mode=result.lookup_mode,
        message=message,
        answer=answer,
        parts=parts,
    )
