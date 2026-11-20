"""Supabase access: upsert chunks and call the SQL search functions
defined in supabase/migrations/001_parts_chunks.sql."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import require_env, supabase_url

TABLE = "parts_chunks"


@lru_cache(maxsize=1)
def client():
    from supabase import create_client

    return create_client(supabase_url(), require_env("SUPABASE_SERVICE_ROLE_KEY"))


def upsert_chunks(rows: list[dict[str, Any]]) -> None:
    client().table(TABLE).upsert(rows, on_conflict="id").execute()


def count_chunks() -> int:
    res = client().table(TABLE).select("id", count="exact").execute()
    return res.count or 0


def _rpc(name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return client().rpc(name, params).execute().data or []


def match_part_no_exact(code: str) -> list[dict[str, Any]]:
    return _rpc("match_part_no_exact", {"code": code})


def match_part_no_ci(code: str) -> list[dict[str, Any]]:
    return _rpc("match_part_no_ci", {"code": code})


def match_sr_no(n: str) -> list[dict[str, Any]]:
    return _rpc("match_sr_no", {"n": n})


def match_description(terms: list[str]) -> list[dict[str, Any]]:
    return _rpc("match_description", {"terms": terms})


def match_vectors(
    embedding: list[float], match_count: int = 8, min_similarity: float = 0.0
) -> list[dict[str, Any]]:
    return _rpc(
        "match_vectors",
        {
            "query_embedding": embedding,
            "match_count": match_count,
            "min_similarity": min_similarity,
        },
    )
