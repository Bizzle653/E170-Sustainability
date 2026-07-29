create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null default '',
  currency text not null default 'USD',
  weekly_digest boolean not null default true,
  market_alerts boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.portfolios (
  user_id uuid primary key references auth.users(id) on delete cascade,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.portfolios enable row level security;

revoke all on table public.profiles from anon;
revoke all on table public.portfolios from anon;
grant select, insert, update on table public.profiles to authenticated;
grant select, insert, update on table public.portfolios to authenticated;

drop policy if exists "Users can read their profile" on public.profiles;
drop policy if exists "Users can create their profile" on public.profiles;
drop policy if exists "Users can update their profile" on public.profiles;
drop policy if exists "Users can read their portfolio" on public.portfolios;
drop policy if exists "Users can create their portfolio" on public.portfolios;
drop policy if exists "Users can update their portfolio" on public.portfolios;

create policy "Users can read their profile"
on public.profiles for select using (auth.uid() = id);
create policy "Users can create their profile"
on public.profiles for insert with check (auth.uid() = id);
create policy "Users can update their profile"
on public.profiles for update using (auth.uid() = id) with check (auth.uid() = id);

create policy "Users can read their portfolio"
on public.portfolios for select using (auth.uid() = user_id);
create policy "Users can create their portfolio"
on public.portfolios for insert with check (auth.uid() = user_id);
create policy "Users can update their portfolio"
on public.portfolios for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', ''));
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
