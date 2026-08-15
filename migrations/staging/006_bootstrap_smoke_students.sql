-- MathAI Staging 006: idempotent synthetic ownership bootstrap.
-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.
-- This script reads auth.users but never creates, updates, or deletes Auth users.

begin;

do $$
declare
  student_a_user_id uuid;
  student_b_user_id uuid;
begin
  select auth_user.id into student_a_user_id
  from auth.users as auth_user
  where pg_catalog.lower(auth_user.email) = 'student-a-staging@example.com';

  select auth_user.id into student_b_user_id
  from auth.users as auth_user
  where pg_catalog.lower(auth_user.email) = 'student-b-staging@example.com';

  if student_a_user_id is null then
    raise exception 'Missing Staging Auth user: student-a-staging@example.com';
  end if;
  if student_b_user_id is null then
    raise exception 'Missing Staging Auth user: student-b-staging@example.com';
  end if;
  if student_a_user_id = student_b_user_id then
    raise exception 'Staging Auth users must have distinct identities';
  end if;

  if exists (
    select 1 from public.learning_students
    where id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
      and display_name <> 'STAGING TEST Student A'
  ) then
    raise exception 'Reserved Student A smoke UUID is already in use';
  end if;
  if exists (
    select 1 from public.learning_students
    where id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
      and display_name <> 'STAGING TEST Student B'
  ) then
    raise exception 'Reserved Student B smoke UUID is already in use';
  end if;
  insert into public.learning_students (id, display_name, active)
  values
    ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'STAGING TEST Student A', true),
    ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'STAGING TEST Student B', true)
  on conflict (id) do update
  set display_name = excluded.display_name,
      active = excluded.active;

  -- Auth users may be deleted and recreated with new UUIDs. These rows are
  -- reserved synthetic identities, so replace only their stale mappings.
  delete from public.student_access
  where student_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    and user_id <> student_a_user_id;
  delete from public.student_access
  where student_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
    and user_id <> student_b_user_id;

  insert into public.student_access (user_id, student_id, role)
  values
    (student_a_user_id, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'owner'),
    (student_b_user_id, 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'owner')
  on conflict (user_id, student_id) do update
  set role = excluded.role;
end $$;

commit;
