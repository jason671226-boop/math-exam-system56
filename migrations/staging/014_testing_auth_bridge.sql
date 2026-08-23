-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.
-- MathAI testing-mode direct-code auth (PROPOSAL — not applied by this file).
--
-- Mirrors production/005_testing_auth_bridge.sql for the isolated Staging
-- project.  Architecture: Supabase Native Email OTP + Postgres Send Email
-- Hook.  NO service_role client usage, NO temporary password, NO password
-- rotation, NO synthetic JWT, NO deterministic UUID.
--
-- Direct-code display is INTERNAL TEST ACCOUNT ONLY:
-- jason601226@gmail.com, jason621226@gmail.com, jason671226@gmail.com.

create table if not exists public.testing_auth_challenges (
  id uuid primary key default extensions.gen_random_uuid(),
  email text not null unique,
  challenge_hash text not null,
  otp text,
  otp_hash text,
  created_at timestamptz not null default pg_catalog.now(),
  expires_at timestamptz not null,
  revealed_at timestamptz,
  consumed_at timestamptz,
  attempt_count integer not null default 0
);

create index if not exists testing_auth_challenges_email_created_idx
  on public.testing_auth_challenges (email, created_at desc);

alter table public.testing_auth_challenges enable row level security;

-- Client roles never read/write the table directly.
revoke all on table public.testing_auth_challenges from public, anon, authenticated;

create or replace function public.mathai_testing_auth_prepare(
  p_email text,
  p_challenge_hash text,
  p_expires_at timestamptz
) returns boolean
language plpgsql security definer set search_path = '' as $$
declare
  v_email text := lower(btrim(coalesce(p_email, '')));
begin
  if v_email not in (
    'jason601226@gmail.com',
    'jason621226@gmail.com',
    'jason671226@gmail.com'
  ) then
    raise exception using errcode = '42501', message = 'testing direct code is internal test accounts only';
  end if;
  if p_challenge_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '42501', message = 'invalid challenge hash';
  end if;
  if p_expires_at <= pg_catalog.now() or p_expires_at > pg_catalog.now() + interval '10 minutes' then
    raise exception using errcode = '42501', message = 'invalid challenge expiry';
  end if;

  insert into public.testing_auth_challenges (
    email, challenge_hash, created_at, expires_at
  ) values (
    v_email, p_challenge_hash, pg_catalog.now(), p_expires_at
  )
  on conflict (email) do update set
    challenge_hash = excluded.challenge_hash,
    otp = null,
    otp_hash = null,
    created_at = pg_catalog.now(),
    expires_at = excluded.expires_at,
    revealed_at = null,
    consumed_at = null,
    attempt_count = 0;

  return true;
end;
$$;

create or replace function public.mathai_testing_auth_reveal(
  p_email text,
  p_challenge_hash text
) returns table (otp text)
language plpgsql security definer set search_path = '' as $$
declare
  challenge_row public.testing_auth_challenges%rowtype;
begin
  p_email := lower(btrim(coalesce(p_email, '')));
  if p_email not in (
    'jason601226@gmail.com',
    'jason621226@gmail.com',
    'jason671226@gmail.com'
  ) then
    raise exception using errcode = '42501', message = 'testing direct code is internal test accounts only';
  end if;
  if p_challenge_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '42501', message = 'invalid challenge hash';
  end if;

  select * into challenge_row
  from public.testing_auth_challenges as challenge
  where lower(challenge.email) = p_email
    and challenge.challenge_hash = p_challenge_hash
    and challenge.consumed_at is null
    and challenge.expires_at > pg_catalog.now();

  if not found then
    raise exception using errcode = '42501', message = 'testing challenge rejected';
  end if;
  if challenge_row.attempt_count >= 5 then
    raise exception using errcode = '42501', message = 'testing challenge locked';
  end if;
  if challenge_row.otp is null or challenge_row.otp !~ '^[0-9]{6}$' then
    raise exception using errcode = '42501', message = 'testing challenge not ready';
  end if;

  update public.testing_auth_challenges
     set revealed_at = coalesce(revealed_at, pg_catalog.now())
   where id = challenge_row.id;

  otp := challenge_row.otp;
  return next;
end;
$$;

create or replace function public.mathai_testing_auth_fail(
  p_email text,
  p_challenge_hash text
) returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  p_email := lower(btrim(coalesce(p_email, '')));
  update public.testing_auth_challenges
     set attempt_count = attempt_count + 1
   where lower(email) = p_email
     and challenge_hash = p_challenge_hash
     and consumed_at is null;
  return true;
end;
$$;

create or replace function public.mathai_testing_auth_consume(
  p_email text,
  p_challenge_hash text
) returns boolean
language plpgsql security definer set search_path = '' as $$
declare
  v_email text := lower(btrim(coalesce(p_email, '')));
begin
  if v_email not in (
    'jason601226@gmail.com',
    'jason621226@gmail.com',
    'jason671226@gmail.com'
  ) then
    raise exception using errcode = '42501', message = 'testing direct code is internal test accounts only';
  end if;
  if p_challenge_hash !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '42501', message = 'invalid challenge hash';
  end if;

  update public.testing_auth_challenges
     set consumed_at = coalesce(consumed_at, pg_catalog.now()),
         otp = ''
   where lower(email) = v_email
     and challenge_hash = p_challenge_hash
     and consumed_at is null
     and expires_at > pg_catalog.now()
     and attempt_count < 5;

  if not found then
    raise exception using errcode = '42501', message = 'testing challenge not consumable';
  end if;

  return true;
end;
$$;

revoke all on function public.mathai_testing_auth_prepare(text,text,timestamptz) from public, anon, authenticated;
revoke all on function public.mathai_testing_auth_reveal(text,text) from public, anon, authenticated;
revoke all on function public.mathai_testing_auth_fail(text,text) from public, anon, authenticated;
revoke all on function public.mathai_testing_auth_consume(text,text) from public, anon, authenticated;
grant execute on function public.mathai_testing_auth_prepare(text,text,timestamptz) to anon;
grant execute on function public.mathai_testing_auth_reveal(text,text) to anon;
grant execute on function public.mathai_testing_auth_fail(text,text) to anon;
-- consume runs after verify_otp, when the client role is authenticated.
grant execute on function public.mathai_testing_auth_consume(text,text) to authenticated;

-- The testing auth flow never uses service_role.  Remove the default EXECUTE
-- privilege that Supabase may assign so the final ACL stays minimal.
revoke execute on function public.mathai_testing_auth_prepare(text,text,timestamptz) from service_role;
revoke execute on function public.mathai_testing_auth_reveal(text,text) from service_role;
revoke execute on function public.mathai_testing_auth_fail(text,text) from service_role;
revoke execute on function public.mathai_testing_auth_consume(text,text) from service_role;

-- Postgres Send Email Hook (executed by supabase_auth_admin).  Configure in
-- Supabase Dashboard -> Authentication -> Hooks -> Send Email Hook.
create or replace function public.mathai_testing_auth_email_hook(payload jsonb)
returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  v_email text := lower(coalesce(payload->'user'->>'email', ''));
  v_token text := coalesce(payload->'email_data'->>'token', '');
  v_token_hash text := coalesce(payload->'email_data'->>'token_hash', '');
  v_action text := coalesce(payload->'email_data'->>'email_action_type', '');
begin
  if v_email not in (
    'jason601226@gmail.com',
    'jason621226@gmail.com',
    'jason671226@gmail.com'
  ) then
    raise exception using errcode = '42501', message = 'email delivery not configured';
  end if;
  if v_token = '' or v_token_hash = '' then
    raise exception using errcode = '42501', message = 'missing otp token';
  end if;

  update public.testing_auth_challenges
     set otp = v_token,
         otp_hash = v_token_hash
   where lower(email) = v_email
     and consumed_at is null
     and expires_at > pg_catalog.now()
     and otp is null;

  if not found then
    raise exception using errcode = '42501', message = 'no open testing challenge';
  end if;

  return '{}'::jsonb;
end;
$$;

revoke all on function public.mathai_testing_auth_email_hook(jsonb) from public, anon, authenticated;
grant execute on function public.mathai_testing_auth_email_hook(jsonb) to supabase_auth_admin;
revoke execute on function public.mathai_testing_auth_email_hook(jsonb) from service_role;
