# Spare Parts RAG Lookup

Looks up spare parts for the **Bajaj Pulsar N-125 (00JZF7ZZ)**, section
**28. Front Wheel Assembly - Disc Brake**, by part number, diagram number or
description, and answers with Claude using only the catalogue rows.

- **Embeddings:** local `fastembed` with `BAAI/bge-small-en-v1.5` (384-dim)
- **Vector store:** Supabase Postgres + `pgvector`
- **LLM:** Claude (`CLAUDE_MODEL`, default `claude-haiku-4-5`)

## How lookups work

| You type | What happens |
|---|---|
| A part number, e.g. `Dh201079` | Case-sensitive exact match first. If nothing matches, case-insensitive match, which returns the stored casing (`DH201079` → `Dh201079`). |
| A diagram number, e.g. `part 13`, `item 12`, `sr no 5`, `#13` | Direct match on Sr. No. |
| Anything else, e.g. `spacer`, `what holds the front wheel on` | Case-insensitive keyword match on descriptions plus vector similarity, keyword hits first. |

Part numbers are never upper- or lower-cased. Claude's reply is checked: any
part code in it that isn't an exact match for a retrieved code is flagged.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in your own values
```

In the Supabase SQL Editor, run these once, in order:

1. `supabase/migrations/001_parts_chunks.sql`: table, indexes, search functions
2. `supabase/migrations/002_grants.sql`: lets the service role key use them

Then load the data (safe to re-run):

```bash
.venv/bin/python ingest.py
```

## Usage

```bash
.venv/bin/python ask.py                  # interactive
.venv/bin/python ask.py --debug          # show route, lookup mode, scores
.venv/bin/python ask.py "part 13"        # one question
.venv/bin/python ask.py --no-llm spacer  # retrieval only, no Claude call
```

## Tests

```bash
.venv/bin/python -m pytest                    # offline: parser, router, casing check
.venv/bin/python scripts/verify.py            # live retrieval checks
.venv/bin/python scripts/verify.py --with-llm # also checks Claude's answers
```

## Layout

```
data/front_wheel_assembly.txt   source table (exact casing)
supabase/migrations/            SQL to run in Supabase
src/parts_rag/                  parser, chunker, embeddings, db, router, retriever, llm
ingest.py  ask.py               entry points
scripts/verify.py  tests/       checks
```
