-- repfind authenticated haul persistence
-- Run this in the Supabase SQL editor for project xacehhtgvubcqdoltazg.

create table if not exists public.repfind_haul_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  product_id text not null,
  name text not null,
  price_usd numeric(10,2) default 0,
  price_cny numeric(10,2) default 0,
  image_url text default '',
  platform text default 'weidian',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, product_id)
);

alter table public.repfind_haul_items enable row level security;

drop policy if exists "Users can read own haul" on public.repfind_haul_items;
create policy "Users can read own haul"
  on public.repfind_haul_items for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert own haul" on public.repfind_haul_items;
create policy "Users can insert own haul"
  on public.repfind_haul_items for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can update own haul" on public.repfind_haul_items;
create policy "Users can update own haul"
  on public.repfind_haul_items for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can delete own haul" on public.repfind_haul_items;
create policy "Users can delete own haul"
  on public.repfind_haul_items for delete
  using (auth.uid() = user_id);

create index if not exists repfind_haul_items_user_created_idx
  on public.repfind_haul_items(user_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_repfind_haul_items_updated_at on public.repfind_haul_items;
create trigger set_repfind_haul_items_updated_at
  before update on public.repfind_haul_items
  for each row execute function public.set_updated_at();
