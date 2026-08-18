-- MathAI v0.8.8 testing-period direct authentication bridge.
-- PURPOSE: show a short code on screen without Email delivery while still
-- establishing a REAL Supabase Auth session before private profile/mastery reads.
--
-- SECURITY BOUNDARIES
-- * TESTING ONLY; remove after Private Beta.
-- * No service_role is used by the Streamlit app.
-- * Only legacy profiles already linked to a real auth.users + student_access row
--   are dynamically allowlisted.
-- * Allowlist expires 2026-09-30 23:59:59 UTC.
-- * Short codes expire after 10 minutes and allow at most 5 failed attempts.
-- * The temporary Auth password is high entropy and must be revoked immediately
--   after exchanging it for a Supabase session.
-- * Private tables remain outside the exposed public schema.

create table if not exists private.testing_login_allowlist (
  email text primary key,
  enabled boolean not null default true,
  expires_at timestamptz not null default timestamptz '2026-09-30 23:59:59+00',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists private.testing_login_challenges (
  email text primary key references private.testing_login_allowlist(email) on delete cascade,
  code_hash text not null,
  expires_at timestamptz not null,
  attempts integer not null default 0 check (attempts between 0 and 10),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

revoke all on table private.testing_login_allowlist from public, anon, authenticated;
revoke all on table private.testing_login_challenges from public, anon, authenticated;

insert into private.testing_login_allowlist (email, enabled, expires_at)
select distinct lower(u.email), true, timestamptz '2026-09-30 23:59:59+00'
from auth.users u
join public.student_access a on a.user_id = u.id and a.role in ('owner','student')
join public.student_profile_controls p
  on p.student_id = a.student_id
  or (p.student_id is null and lower(p.email) = lower(u.email))
where coalesce(lower(u.email), '') <> ''
on conflict (email) do update
set enabled = true,
    expires_at = excluded.expires_at,
    updated_at = now();

create or replace function public.mathai_testing_issue_login_code(p_email text)
returns table(code text, expires_at timestamptz)
language plpgsql security definer set search_path = ''
as $$
declare
  normalized_email text := lower(trim(coalesce(p_email, '')));
  raw_bytes bytea;
  numeric_code bigint;
  generated_code text;
  challenge_expires timestamptz := now() + interval '10 minutes';
begin
  if normalized_email = '' then
    raise exception using errcode='22023', message='testing login unavailable';
  end if;
  if not exists (
    select 1 from private.testing_login_allowlist a
    where a.email=normalized_email and a.enabled and a.expires_at>now()
  ) then
    raise exception using errcode='42501', message='testing login unavailable';
  end if;
  if not exists (
    select 1 from auth.users u
    join public.student_access sa on sa.user_id=u.id and sa.role in ('owner','student')
    join public.student_profile_controls p on p.student_id=sa.student_id
    where lower(u.email)=normalized_email
  ) then
    raise exception using errcode='42501', message='testing login unavailable';
  end if;

  raw_bytes := extensions.gen_random_bytes(4);
  numeric_code := (
    pg_catalog.get_byte(raw_bytes,0)::bigint*16777216
    + pg_catalog.get_byte(raw_bytes,1)::bigint*65536
    + pg_catalog.get_byte(raw_bytes,2)::bigint*256
    + pg_catalog.get_byte(raw_bytes,3)::bigint
  ) % 1000000;
  generated_code := pg_catalog.lpad(numeric_code::text,6,'0');

  insert into private.testing_login_challenges
    (email,code_hash,expires_at,attempts,created_at,updated_at)
  values
    (normalized_email,extensions.crypt(generated_code,extensions.gen_salt('bf',8)),
     challenge_expires,0,now(),now())
  on conflict (email) do update
  set code_hash=excluded.code_hash, expires_at=excluded.expires_at,
      attempts=0, created_at=excluded.created_at, updated_at=excluded.updated_at;

  return query select generated_code, challenge_expires;
end;
$$;

create or replace function public.mathai_testing_verify_login_code(p_email text,p_code text)
returns table(temp_password text)
language plpgsql security definer set search_path = ''
as $$
declare
  normalized_email text := lower(trim(coalesce(p_email,'')));
  clean_code text := trim(coalesce(p_code,''));
  challenge private.testing_login_challenges%rowtype;
  generated_password text;
  resolved_user_id uuid;
begin
  if normalized_email='' or clean_code='' then
    raise exception using errcode='22023', message='invalid testing code';
  end if;
  if not exists (
    select 1 from private.testing_login_allowlist a
    where a.email=normalized_email and a.enabled and a.expires_at>now()
  ) then
    raise exception using errcode='42501', message='testing login unavailable';
  end if;

  select * into challenge from private.testing_login_challenges c
  where c.email=normalized_email for update;
  if challenge.email is null or challenge.expires_at<=now() then
    delete from private.testing_login_challenges where email=normalized_email;
    raise exception using errcode='22023', message='testing code expired';
  end if;
  if challenge.attempts>=5 then
    delete from private.testing_login_challenges where email=normalized_email;
    raise exception using errcode='42501', message='too many attempts';
  end if;
  if extensions.crypt(clean_code,challenge.code_hash)<>challenge.code_hash then
    update private.testing_login_challenges
    set attempts=attempts+1,updated_at=now() where email=normalized_email;
    raise exception using errcode='22023', message='invalid testing code';
  end if;

  generated_password := pg_catalog.encode(extensions.gen_random_bytes(32),'hex');
  update auth.users u
  set encrypted_password=extensions.crypt(generated_password,extensions.gen_salt('bf',10)),
      email_confirmed_at=coalesce(u.email_confirmed_at,now()),
      raw_user_meta_data=pg_catalog.jsonb_set(coalesce(u.raw_user_meta_data,'{}'::jsonb),
                                             '{email_verified}','true'::jsonb,true),
      updated_at=now()
  where lower(u.email)=normalized_email
    and exists (select 1 from public.student_access sa
                where sa.user_id=u.id and sa.role in ('owner','student'))
  returning u.id into resolved_user_id;
  if resolved_user_id is null then
    raise exception using errcode='42501', message='testing login unavailable';
  end if;

  update auth.identities i
  set identity_data=pg_catalog.jsonb_set(coalesce(i.identity_data,'{}'::jsonb),
                                         '{email_verified}','true'::jsonb,true),
      updated_at=now()
  where i.user_id=resolved_user_id and i.provider='email';

  delete from private.testing_login_challenges where email=normalized_email;
  return query select generated_password;
end;
$$;

create or replace function public.mathai_testing_revoke_temp_password(
  p_email text,p_temp_password text
)
returns boolean
language plpgsql security definer set search_path = ''
as $$
declare
  normalized_email text := lower(trim(coalesce(p_email,'')));
  clean_password text := coalesce(p_temp_password,'');
  changed boolean := false;
begin
  if normalized_email='' or clean_password='' then return false; end if;
  update auth.users u
  set encrypted_password=extensions.crypt(
        pg_catalog.encode(extensions.gen_random_bytes(48),'hex'),
        extensions.gen_salt('bf',10)),
      updated_at=now()
  where lower(u.email)=normalized_email
    and exists (select 1 from private.testing_login_allowlist a
                where a.email=normalized_email and a.enabled and a.expires_at>now())
    and extensions.crypt(clean_password,u.encrypted_password)=u.encrypted_password;
  changed := found;
  return changed;
end;
$$;

create or replace function public.mathai_testing_consume_login_password()
returns boolean
language plpgsql security definer set search_path = ''
as $$
declare
  caller_id uuid := (select auth.uid());
  caller_email text := lower(coalesce(auth.jwt()->>'email',''));
begin
  if caller_id is null or caller_email='' then
    raise exception using errcode='42501', message='authentication required';
  end if;
  if not exists (select 1 from private.testing_login_allowlist a
                 where a.email=caller_email and a.enabled and a.expires_at>now()) then
    return false;
  end if;
  update auth.users u
  set encrypted_password=extensions.crypt(
        pg_catalog.encode(extensions.gen_random_bytes(48),'hex'),
        extensions.gen_salt('bf',10)),
      updated_at=now()
  where u.id=caller_id and lower(u.email)=caller_email;
  return found;
end;
$$;

revoke all on function public.mathai_testing_issue_login_code(text) from public;
revoke all on function public.mathai_testing_verify_login_code(text,text) from public;
revoke all on function public.mathai_testing_revoke_temp_password(text,text) from public;
revoke all on function public.mathai_testing_consume_login_password() from public;
revoke execute on function public.mathai_testing_consume_login_password() from anon;

grant execute on function public.mathai_testing_issue_login_code(text) to anon,authenticated;
grant execute on function public.mathai_testing_verify_login_code(text,text) to anon,authenticated;
grant execute on function public.mathai_testing_revoke_temp_password(text,text) to anon,authenticated;
grant execute on function public.mathai_testing_consume_login_password() to authenticated;

-- ROLLBACK AFTER TESTING:
-- drop function if exists public.mathai_testing_consume_login_password();
-- drop function if exists public.mathai_testing_revoke_temp_password(text,text);
-- drop function if exists public.mathai_testing_verify_login_code(text,text);
-- drop function if exists public.mathai_testing_issue_login_code(text);
-- drop table if exists private.testing_login_challenges;
-- drop table if exists private.testing_login_allowlist;
