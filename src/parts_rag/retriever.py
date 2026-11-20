"""Hybrid retrieval.

1. Part code  -> case-sensitive exact match; only if 0 rows, ILIKE fallback.
2. Sr. No.    -> direct sr_no match.
3. Otherwise  -> case-insensitive keyword match on descriptions (catches every
                 matching row) + pgvector cosine search, merged. Keyword hits
                 rank above vector-only hits. The summary chunk is only kept
                 for whole-assembly questions.

Results always carry the stored metadata, so part numbers come back in their
true casing (e.g. "DH201079" -> "Dh201079").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import db
from .embeddings import embed_query
from .query_router import Route, route

VECTOR_TOP_K = 5
VECTOR_MIN_SIMILARITY = 0.60   # bge-small cosine; tuned on this table
VECTOR_ONLY_KEEP = 3           # vector-only rows kept when there are keyword hits


@dataclass
class Hit:
    id: str
    content: str
    metadata: dict[str, Any]
    source: str                  # exact | ci_fallback | sr_no | keyword | vector | keyword+vector
    similarity: float | None = None
    matched_terms: int | None = None

    @property
    def is_row(self) -> bool:
        return self.metadata.get("chunk_type") == "row"


@dataclass
class Result:
    query: str
    route: Route
    hits: list[Hit] = field(default_factory=list)
    lookup_mode: str = ""        # exact | ci_fallback | none | sr_no | hybrid
    notes: list[str] = field(default_factory=list)

    @property
    def rows(self) -> list[Hit]:
        return [h for h in self.hits if h.is_row]


def _hits(rows: list[dict[str, Any]], source: str) -> list[Hit]:
    return [
        Hit(
            id=r["id"],
            content=r["content"],
            metadata=r["metadata"],
            source=source,
            similarity=r.get("similarity"),
            matched_terms=r.get("matched_terms"),
        )
        for r in rows
    ]


def _summary_hit() -> list[Hit]:
    """Fetch the summary chunk via vector search on a neutral query."""
    rows = db.match_vectors(embed_query("full parts list of the assembly"), match_count=17)
    return [h for h in _hits(rows, "vector") if h.metadata.get("chunk_type") == "summary"][:1]


def retrieve(query: str) -> Result:
    r = route(query)
    res = Result(query=query, route=r)

    if r.mode == "part_no":
        exact = db.match_part_no_exact(r.value)
        if exact:
            res.hits, res.lookup_mode = _hits(exact, "exact"), "exact"
        else:
            ci = db.match_part_no_ci(r.value)
            if ci:
                res.hits, res.lookup_mode = _hits(ci, "ci_fallback"), "ci_fallback"
                stored = ", ".join(h.metadata["part_no"] for h in res.hits)
                res.notes.append(f"No exact match for {r.value!r}; case-insensitive match found: {stored}")
            else:
                res.lookup_mode = "none"
                res.notes.append(f"Part No. {r.value!r} not found (exact or case-insensitive).")

    elif r.mode == "sr_no":
        rows = db.match_sr_no(r.value)
        res.hits, res.lookup_mode = _hits(rows, "sr_no"), "sr_no"
        if not rows:
            res.notes.append(f"No item with Sr. No. {r.value} in this assembly.")

    else:
        res.lookup_mode = "hybrid"
        keyword = _hits(db.match_description(r.terms), "keyword") if r.terms else []
        vector = _hits(
            db.match_vectors(embed_query(query), VECTOR_TOP_K, VECTOR_MIN_SIMILARITY),
            "vector",
        )
        by_id: dict[str, Hit] = {h.id: h for h in keyword}
        vector_only: list[Hit] = []
        for v in vector:
            if v.id in by_id:
                by_id[v.id].source = "keyword+vector"
                by_id[v.id].similarity = v.similarity
            elif v.is_row:
                vector_only.append(v)
        merged = sorted(
            by_id.values(),
            key=lambda h: (-(h.matched_terms or 0), -(h.similarity or 0.0), h.id),
        )
        if merged:
            merged += vector_only[:VECTOR_ONLY_KEEP]
        else:
            merged = vector_only
        res.hits = merged
        if not res.hits:
            res.notes.append("No matching rows by keyword or meaning.")

    if r.whole_assembly and not any(h.id.endswith("-summary") for h in res.hits):
        res.hits = _summary_hit() + res.hits

    return res
