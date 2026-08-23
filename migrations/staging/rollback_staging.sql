-- MathAI Staging emergency rollback: removes objects created by 001-010.
-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.
-- This is not the normal application rollback path. Prefer reverting the app
-- deployment and preserving all learning data. Run this script only after a
-- verified Staging backup and only when the guards below allow it.

begin;

do $$
begin
  if not exists (
    select 1 from auth.users
    where pg_catalog.lower(email) = 'student-a-staging@example.com'
  ) or not exists (
    select 1 from auth.users
    where pg_catalog.lower(email) = 'student-b-staging@example.com'
  ) then
    raise exception 'STAGING ONLY: reserved synthetic Auth users are missing';
  end if;

  if exists (
    select 1 from public.learning_students
    where id not in (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid,
      'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'::uuid
    )
  ) then
    raise exception 'REFUSED: non-synthetic students exist';
  end if;

  if exists (
    select 1 from public.diagnostic_attempts where profile_id <> 'STAGING_SMOKE'
  ) or exists (
    select 1 from public.knowledge_mastery where profile_id <> 'STAGING_SMOKE'
  ) or exists (
    select 1 from public.thinking_skill_evidence where profile_id <> 'STAGING_SMOKE'
  ) or exists (
    select 1 from public.teacher_feedback where profile_id <> 'STAGING_SMOKE'
  ) then
    raise exception 'REFUSED: non-smoke learning data exists';
  end if;
end
$$;

drop table if exists public.teacher_feedback;
drop table if exists public.teacher_access;

alter table public.student_access
  drop constraint if exists student_access_role_check;
alter table public.student_access
  add constraint student_access_role_check
  check (role in ('owner', 'student', 'guardian'));

drop policy if exists thinking_skill_evidence_update_owned on public.thinking_skill_evidence;
drop policy if exists thinking_skill_evidence_insert_owned on public.thinking_skill_evidence;
drop policy if exists thinking_skill_evidence_select_owned on public.thinking_skill_evidence;
drop policy if exists knowledge_mastery_update_owned on public.knowledge_mastery;
drop policy if exists knowledge_mastery_insert_owned on public.knowledge_mastery;
drop policy if exists knowledge_mastery_select_owned on public.knowledge_mastery;
drop policy if exists diagnostic_item_results_update_owned on public.diagnostic_item_results;
drop policy if exists diagnostic_item_results_insert_owned on public.diagnostic_item_results;
drop policy if exists diagnostic_item_results_select_owned on public.diagnostic_item_results;
drop policy if exists diagnostic_attempts_update_owned on public.diagnostic_attempts;
drop policy if exists diagnostic_attempts_insert_owned on public.diagnostic_attempts;
drop policy if exists diagnostic_attempts_select_owned on public.diagnostic_attempts;
drop policy if exists student_access_select_own on public.student_access;

revoke execute on function private.can_access_student(uuid) from authenticated;
drop function if exists private.can_access_student(uuid);

drop trigger if exists thinking_skill_evidence_set_updated_at on public.thinking_skill_evidence;
drop trigger if exists knowledge_mastery_set_updated_at on public.knowledge_mastery;
drop trigger if exists learning_students_set_updated_at on public.learning_students;

drop table if exists public.diagnostic_item_results;
drop table if exists public.diagnostic_attempts;
drop table if exists public.thinking_skill_evidence;
drop table if exists public.knowledge_mastery;
drop table if exists public.student_access;
drop table if exists public.learning_students;

drop function if exists private.set_updated_at();

revoke usage on schema private from authenticated;

-- Do not drop private/extensions schemas or pgcrypto: they may predate this package.
commit;
