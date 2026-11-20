-- Grants for the Python app (service_role key). Run once in the Supabase
-- SQL Editor after 001_parts_chunks.sql. Safe to re-run.
--
-- Newer Supabase projects do not auto-grant privileges on tables created in
-- the SQL Editor, so the service_role needs explicit grants.

grant usage on schema public to service_role;

grant select, insert, update, delete on public.parts_chunks to service_role;

grant execute on function public.escape_like(text)                  to service_role;
grant execute on function public.match_part_no_exact(text)          to service_role;
grant execute on function public.match_part_no_ci(text)             to service_role;
grant execute on function public.match_sr_no(text)                  to service_role;
grant execute on function public.match_description(text[])          to service_role;
grant execute on function public.match_vectors(vector, int, float)  to service_role;

-- Keep the public (anon) and signed-in (authenticated) API roles out.
revoke all on public.parts_chunks from anon, authenticated;
revoke execute on function public.match_part_no_exact(text)          from public, anon, authenticated;
revoke execute on function public.match_part_no_ci(text)             from public, anon, authenticated;
revoke execute on function public.match_sr_no(text)                  from public, anon, authenticated;
revoke execute on function public.match_description(text[])          from public, anon, authenticated;
revoke execute on function public.match_vectors(vector, int, float)  from public, anon, authenticated;
