-- Analytics must be write-only from the public browser client.
-- This migration intentionally removes all anonymous/authenticated read access
-- while preserving INSERT-only telemetry if analytics is re-enabled later.
do $$
declare
  target_table text;
  policy_name text;
begin
  foreach target_table in array array['repfind_page_views', 'repfind_events', 'repfind_searches']
  loop
    execute format('alter table public.%I enable row level security', target_table);

    for policy_name in
      select policyname
      from pg_policies
      where schemaname = 'public'
        and tablename = target_table
        and cmd in ('SELECT', 'ALL')
    loop
      execute format('drop policy if exists %I on public.%I', policy_name, target_table);
    end loop;

    execute format('revoke select, update, delete on public.%I from anon, authenticated', target_table);
    execute format('grant insert on public.%I to anon, authenticated', target_table);
    execute format('drop policy if exists %I on public.%I', 'Browser clients can insert analytics', target_table);
    execute format(
      'create policy %I on public.%I for insert to anon, authenticated with check (true)',
      'Browser clients can insert analytics', target_table
    );
  end loop;
end $$;
