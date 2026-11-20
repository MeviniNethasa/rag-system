-- Spare parts RAG: table, indexes and search functions.
-- Run once in the Supabase SQL Editor (safe to re-run).

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------
create table if not exists public.parts_chunks (
    id          text primary key,              -- e.g. '28-row-16', '28-summary'
    content     text not null,
    metadata    jsonb not null default '{}'::jsonb,
    embedding   vector(384) not null,          -- BAAI/bge-small-en-v1.5
    created_at  timestamptz not null default now()
);

-- RLS on with no policies: the anon key cannot read or write this table.
-- The Python app uses the service role key, which bypasses RLS.
alter table public.parts_chunks enable row level security;

create index if not exists parts_chunks_part_no_idx
    on public.parts_chunks ((metadata->>'part_no'));
create index if not exists parts_chunks_part_no_lower_idx
    on public.parts_chunks (lower(metadata->>'part_no'));
create index if not exists parts_chunks_sr_no_idx
    on public.parts_chunks ((metadata->>'sr_no'));
-- 17 rows: an exact vector scan is fast, so no ANN (hnsw/ivfflat) index yet.

-- ---------------------------------------------------------------------------
-- Helper: escape LIKE/ILIKE wildcards so user input is matched literally.
-- ---------------------------------------------------------------------------
create or replace function public.escape_like(input text)
returns text
language sql
immutable
set search_path = public, extensions
as $$
    select replace(replace(replace(input, '\', '\\'), '%', '\%'), '_', '\_');
$$;

-- ---------------------------------------------------------------------------
-- 1a. Part No. strict lookup (case-sensitive equality)
-- ---------------------------------------------------------------------------
create or replace function public.match_part_no_exact(code text)
returns table (id text, content text, metadata jsonb)
language sql
stable
set search_path = public, extensions
as $$
    select c.id, c.content, c.metadata
    from public.parts_chunks c
    where c.metadata->>'chunk_type' = 'row'
      and c.metadata->>'part_no' = code
    order by c.id;
$$;

-- ---------------------------------------------------------------------------
-- 1b. Part No. fallback (case-insensitive equality, wildcards escaped).
-- Returns the stored casing in metadata, e.g. 'DH201079' finds 'Dh201079'.
-- ---------------------------------------------------------------------------
create or replace function public.match_part_no_ci(code text)
returns table (id text, content text, metadata jsonb)
language sql
stable
set search_path = public, extensions
as $$
    select c.id, c.content, c.metadata
    from public.parts_chunks c
    where c.metadata->>'chunk_type' = 'row'
      and c.metadata->>'part_no' ilike public.escape_like(code)
    order by c.id;
$$;

-- ---------------------------------------------------------------------------
-- 2. Diagram Sr. No. lookup
-- ---------------------------------------------------------------------------
create or replace function public.match_sr_no(n text)
returns table (id text, content text, metadata jsonb)
language sql
stable
set search_path = public, extensions
as $$
    select c.id, c.content, c.metadata
    from public.parts_chunks c
    where c.metadata->>'chunk_type' = 'row'
      and c.metadata->>'sr_no' = n
    order by c.id;
$$;

-- ---------------------------------------------------------------------------
-- 3a. Description keyword search (case-insensitive substring per term).
-- Rows matching more terms rank first.
-- ---------------------------------------------------------------------------
create or replace function public.match_description(terms text[])
returns table (id text, content text, metadata jsonb, matched_terms int)
language sql
stable
set search_path = public, extensions
as $$
    select c.id, c.content, c.metadata, m.matched_terms
    from public.parts_chunks c
    cross join lateral (
        select count(*)::int as matched_terms
        from unnest(terms) as t(term)
        where length(trim(t.term)) > 0
          and c.metadata->>'description'
              ilike '%' || public.escape_like(trim(t.term)) || '%'
    ) m
    where c.metadata->>'chunk_type' = 'row'
      and m.matched_terms > 0
    order by m.matched_terms desc, c.id;
$$;

-- ---------------------------------------------------------------------------
-- 3b. Vector search (cosine similarity). Includes the summary chunk.
-- ---------------------------------------------------------------------------
create or replace function public.match_vectors(
    query_embedding vector(384),
    match_count int default 8,
    min_similarity float default 0.0
)
returns table (id text, content text, metadata jsonb, similarity float)
language sql
stable
set search_path = public, extensions
as $$
    select c.id, c.content, c.metadata,
           1 - (c.embedding <=> query_embedding) as similarity
    from public.parts_chunks c
    where 1 - (c.embedding <=> query_embedding) >= min_similarity
    order by c.embedding <=> query_embedding
    limit match_count;
$$;
