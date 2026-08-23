-- MathAI v0.8.8.2: verified-email self-registration provisioning.
-- Additive and idempotent. No user data is deleted or rewritten.

begin;

create or replace function public.mathai_private_ensure_student()
returns table(student_id uuid, created boolean)
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := (select auth.uid());
  verified_email text := lower(coalesce(auth.jwt()->>'email', ''));
  resolved_id uuid;
  made boolean := false;
begin
  if caller_id is null or verified_email = '' then
    raise exception using errcode = '42501', message = 'verified authentication required';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(caller_id::text, 0)
  );

  select access.student_id
    into resolved_id
  from public.student_access as access
  where access.user_id = caller_id
    and access.role in ('owner', 'student')
  order by access.created_at
  limit 1;

  if resolved_id is null then
    insert into public.learning_students (legacy_email, display_name, active)
    values (verified_email, '', true)
    returning id into resolved_id;

    insert into public.student_access (user_id, student_id, role)
    values (caller_id, resolved_id, 'owner');

    made := true;
  end if;

  return query select resolved_id, made;
end;
$$;

revoke all on function public.mathai_private_ensure_student() from public, anon;
grant execute on function public.mathai_private_ensure_student() to authenticated;

commit;
