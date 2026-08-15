-- MathAI Staging rollback: removes only objects created by 001-003.
-- Review dependencies and take a staging backup before running.

begin;

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
