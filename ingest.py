"""Parse -> chunk -> embed -> upsert into Supabase. Safe to re-run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from parts_rag import db  # noqa: E402
from parts_rag.chunker import build_chunks  # noqa: E402
from parts_rag.config import DATA_FILE  # noqa: E402
from parts_rag.embeddings import embed_passages  # noqa: E402
from parts_rag.parser import parse_file  # noqa: E402


def main() -> int:
    assembly = parse_file(DATA_FILE)
    chunks = build_chunks(assembly)
    print(f"Parsed {len(assembly.rows)} rows -> {len(chunks)} chunks "
          f"({assembly.model_label}, {assembly.assembly_label})")

    vectors = embed_passages([c.content for c in chunks])
    print(f"Embedded {len(vectors)} chunks ({len(vectors[0])}-dim)")

    db.upsert_chunks([
        {"id": c.id, "content": c.content, "metadata": c.metadata, "embedding": v}
        for c, v in zip(chunks, vectors)
    ])
    total = db.count_chunks()
    print(f"Upserted. parts_chunks now has {total} rows.")
    return 0 if total == len(chunks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
