"""Local embeddings with fastembed (BAAI/bge-small-en-v1.5, 384-dim).

Passages and queries are embedded differently: query_embed adds the BGE
"Represent this sentence for searching relevant passages:" instruction.
"""

from __future__ import annotations

from functools import lru_cache

from .config import EMBEDDING_DIM, EMBEDDING_MODEL


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=EMBEDDING_MODEL)


def _check(vec) -> list[float]:
    out = [float(x) for x in vec]
    if len(out) != EMBEDDING_DIM:
        raise ValueError(f"Expected {EMBEDDING_DIM}-dim embedding, got {len(out)}")
    return out


def embed_passages(texts: list[str]) -> list[list[float]]:
    return [_check(v) for v in _model().passage_embed(texts)]


def embed_query(text: str) -> list[float]:
    return _check(next(iter(_model().query_embed(text))))
