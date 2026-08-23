-- MathAI Staging 011: authenticated profile/wallet ownership hardening.
-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.

begin;

create table if not exists public.student_profile_controls (
  student_id uuid primary key references public.learning_students(id) on delete cascade,
  email text unique,
  identity_locked boolean not null default false,
  locked_last_name text not null default '',
  locked_first_name text not null default '',
  city text not null default '',
  district text not null default '',
  school text not null default '',
  grade text not null default '',
  version text not null default '',
  traits jsonb not null default '[]'::jsonb,
  interests jsonb not null default '[]'::jsonb,
  discovery_source text not null default '',
  source_detail text not null default '',
  source_reward_status text not null default 'none',
  referral_eligible_override boolean not null default false,
  change_year integer not null default extract(year from pg_catalog.now())::integer,
  change_count integer not null default 0 check (change_count >= 0),
  updated_at timestamptz not null default pg_catalog.now()
);

create table if not exists public.member_wallets (
  student_id uuid primary key references public.learning_students(id) on delete cascade,
  email text unique,
  credits integer not null default 200 check (credits >= 0),
  created_at timestamptz not null default pg_catalog.now(),
  updated_at timestamptz not null default pg_catalog.now()
);

create table if not exists public.member_credit_ledger (
  id uuid primary key default extensions.gen_random_uuid(),
  student_id uuid not null references public.learning_students(id) on delete cascade,
  delta integer not null check (delta <> 0),
  balance_after integer not null check (balance_after >= 0),
  reason text not null,
  reference_id text not null,
  created_at timestamptz not null default pg_catalog.now(),
  unique (student_id, reason, reference_id)
);

alter table public.student_profile_controls enable row level security;
alter table public.member_wallets enable row level security;
alter table public.member_credit_ledger enable row level security;
revoke all on public.student_profile_controls from public, anon, authenticated;
revoke all on public.member_wallets from public, anon, authenticated;
revoke all on public.member_credit_ledger from public, anon, authenticated;

create or replace function private.current_student_id()
returns uuid
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  caller_id uuid := (select auth.uid());
  resolved_student_id uuid;
begin
  if caller_id is null then
    raise exception using errcode = '42501', message = 'authentication required';
  end if;
  select access.student_id
    into resolved_student_id
  from public.student_access as access
  where access.user_id = caller_id
    and access.role in ('owner', 'student')
  order by access.created_at
  limit 1;
  if resolved_student_id is null then
    raise exception using errcode = '42501', message = 'student access required';
  end if;
  return resolved_student_id;
end;
$$;

revoke all on function private.current_student_id() from public, anon;
grant execute on function private.current_student_id() to authenticated;

create or replace function public.mathai_private_profile_get()
returns table (
  found boolean, identity_locked boolean, locked_last_name text,
  locked_first_name text, city text, district text, school text,
  grade text, version text, traits jsonb, interests jsonb,
  discovery_source text, source_detail text, source_reward_status text,
  referral_eligible_override boolean, change_year integer, change_count integer
)
language sql
stable
security definer
set search_path = ''
as $$
  select true, p.identity_locked, p.locked_last_name, p.locked_first_name,
    p.city, p.district, p.school, p.grade, p.version, p.traits, p.interests,
    p.discovery_source, p.source_detail, p.source_reward_status,
    p.referral_eligible_override, p.change_year, p.change_count
  from public.student_profile_controls as p
  where p.student_id = private.current_student_id();
$$;

create or replace function public.mathai_private_profile_save(
  p_identity_locked boolean,
  p_locked_last_name text,
  p_locked_first_name text,
  p_city text,
  p_district text,
  p_school text,
  p_grade text,
  p_version text,
  p_traits jsonb,
  p_interests jsonb,
  p_discovery_source text,
  p_source_detail text,
  p_source_reward_status text,
  p_referral_eligible_override boolean,
  p_change_year integer,
  p_change_count integer
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_student_id uuid := private.current_student_id();
  caller_email text := pg_catalog.lower(coalesce(auth.jwt() ->> 'email', ''));
begin
  insert into public.student_profile_controls (
    student_id, email, identity_locked, locked_last_name, locked_first_name,
    city, district, school, grade, version, traits, interests,
    discovery_source, source_detail, source_reward_status,
    referral_eligible_override, change_year, change_count, updated_at
  ) values (
    target_student_id, nullif(caller_email, ''),
    coalesce(p_identity_locked, false),
    pg_catalog.btrim(coalesce(p_locked_last_name, '')),
    pg_catalog.btrim(coalesce(p_locked_first_name, '')),
    pg_catalog.btrim(coalesce(p_city, '')),
    pg_catalog.btrim(coalesce(p_district, '')),
    pg_catalog.btrim(coalesce(p_school, '')),
    pg_catalog.btrim(coalesce(p_grade, '')),
    pg_catalog.btrim(coalesce(p_version, '')),
    coalesce(p_traits, '[]'::jsonb),
    coalesce(p_interests, '[]'::jsonb),
    pg_catalog.btrim(coalesce(p_discovery_source, '')),
    pg_catalog.btrim(coalesce(p_source_detail, '')),
    coalesce(nullif(pg_catalog.btrim(p_source_reward_status), ''), 'none'),
    coalesce(p_referral_eligible_override, false),
    coalesce(p_change_year, extract(year from pg_catalog.now())::integer),
    greatest(coalesce(p_change_count, 0), 0),
    pg_catalog.now()
  )
  on conflict (student_id) do update set
    identity_locked = excluded.identity_locked,
    locked_last_name = excluded.locked_last_name,
    locked_first_name = excluded.locked_first_name,
    city = excluded.city, district = excluded.district, school = excluded.school,
    grade = excluded.grade, version = excluded.version,
    traits = excluded.traits, interests = excluded.interests,
    discovery_source = excluded.discovery_source,
    source_detail = excluded.source_detail,
    source_reward_status = excluded.source_reward_status,
    referral_eligible_override = excluded.referral_eligible_override,
    change_year = excluded.change_year, change_count = excluded.change_count,
    updated_at = excluded.updated_at;
  return true;
end;
$$;

create or replace function public.mathai_private_wallet_bootstrap()
returns table (credits integer, created boolean)
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_student_id uuid := private.current_student_id();
  caller_email text := pg_catalog.lower(coalesce(auth.jwt() ->> 'email', ''));
  inserted boolean := false;
  current_credits integer;
begin
  insert into public.member_wallets (student_id, email, credits)
  values (target_student_id, nullif(caller_email, ''), 200)
  on conflict (student_id) do nothing;
  inserted := found;
  select wallet.credits into current_credits
  from public.member_wallets as wallet
  where wallet.student_id = target_student_id;
  return query select current_credits, inserted;
end;
$$;

create or replace function public.mathai_private_wallet_lookup()
returns table (found boolean, credits integer)
language sql
stable
security definer
set search_path = ''
as $$
  select true, wallet.credits
  from public.member_wallets as wallet
  where wallet.student_id = private.current_student_id();
$$;

create or replace function public.mathai_private_wallet_debit(
  p_amount integer,
  p_reason text,
  p_reference_id text
)
returns table (success boolean, new_balance integer, applied boolean)
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_student_id uuid := private.current_student_id();
  amount integer := coalesce(p_amount, 0);
  safe_reason text := pg_catalog.btrim(coalesce(p_reason, ''));
  safe_reference text := pg_catalog.btrim(coalesce(p_reference_id, ''));
  current_balance integer;
begin
  if amount <= 0 or safe_reference = '' or safe_reason not in ('ai_usage_charge', 'diagnostic_practice') then
    raise exception using errcode = '22023', message = 'invalid debit request';
  end if;
  perform 1 from public.member_credit_ledger
  where student_id = target_student_id
    and reason = safe_reason
    and reference_id = safe_reference;
  if found then
    select credits into current_balance from public.member_wallets
    where student_id = target_student_id;
    return query select true, current_balance, false;
    return;
  end if;
  update public.member_wallets
  set credits = credits - amount, updated_at = pg_catalog.now()
  where student_id = target_student_id and credits >= amount
  returning credits into current_balance;
  if current_balance is null then
    return query select false, coalesce((
      select credits from public.member_wallets where student_id = target_student_id
    ), 0), false;
    return;
  end if;
  insert into public.member_credit_ledger (
    student_id, delta, balance_after, reason, reference_id
  ) values (target_student_id, -amount, current_balance, safe_reason, safe_reference);
  return query select true, current_balance, true;
end;
$$;

revoke all on function public.mathai_private_profile_get() from public, anon;
revoke all on function public.mathai_private_profile_save(boolean,text,text,text,text,text,text,text,jsonb,jsonb,text,text,text,boolean,integer,integer) from public, anon;
revoke all on function public.mathai_private_wallet_bootstrap() from public, anon;
revoke all on function public.mathai_private_wallet_lookup() from public, anon;
revoke all on function public.mathai_private_wallet_debit(integer,text,text) from public, anon;
grant execute on function public.mathai_private_profile_get() to authenticated;
grant execute on function public.mathai_private_profile_save(boolean,text,text,text,text,text,text,text,jsonb,jsonb,text,text,text,boolean,integer,integer) to authenticated;
grant execute on function public.mathai_private_wallet_bootstrap() to authenticated;
grant execute on function public.mathai_private_wallet_lookup() to authenticated;
grant execute on function public.mathai_private_wallet_debit(integer,text,text) to authenticated;

commit;
