-- MathAI Staging 003: student ownership RLS

begin;

revoke all on schema private from public;
grant usage on schema private to authenticated;

create or replace function private.can_access_student(requested_student_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.student_access as access
    where access.user_id = (select auth.uid())
      and access.student_id = requested_student_id
  );
$$;

revoke all on function private.can_access_student(uuid) from public;
grant execute on function private.can_access_student(uuid) to authenticated;

grant select on public.student_access to authenticated;
grant select, insert, update on public.diagnostic_attempts to authenticated;
grant select, insert, update on public.diagnostic_item_results to authenticated;
grant select, insert, update on public.knowledge_mastery to authenticated;
grant select, insert, update on public.thinking_skill_evidence to authenticated;

create policy student_access_select_own on public.student_access
for select to authenticated using (user_id = (select auth.uid()));

create policy diagnostic_attempts_select_owned on public.diagnostic_attempts
for select to authenticated using (private.can_access_student(student_id));
create policy diagnostic_attempts_insert_owned on public.diagnostic_attempts
for insert to authenticated with check (private.can_access_student(student_id));
create policy diagnostic_attempts_update_owned on public.diagnostic_attempts
for update to authenticated using (private.can_access_student(student_id))
with check (private.can_access_student(student_id));

create policy diagnostic_item_results_select_owned on public.diagnostic_item_results
for select to authenticated using (exists (
  select 1 from public.diagnostic_attempts as attempt
  where attempt.id = diagnostic_item_results.attempt_id
    and private.can_access_student(attempt.student_id)
));
create policy diagnostic_item_results_insert_owned on public.diagnostic_item_results
for insert to authenticated with check (exists (
  select 1 from public.diagnostic_attempts as attempt
  where attempt.id = diagnostic_item_results.attempt_id
    and private.can_access_student(attempt.student_id)
));
create policy diagnostic_item_results_update_owned on public.diagnostic_item_results
for update to authenticated using (exists (
  select 1 from public.diagnostic_attempts as attempt
  where attempt.id = diagnostic_item_results.attempt_id
    and private.can_access_student(attempt.student_id)
)) with check (exists (
  select 1 from public.diagnostic_attempts as attempt
  where attempt.id = diagnostic_item_results.attempt_id
    and private.can_access_student(attempt.student_id)
));

create policy knowledge_mastery_select_owned on public.knowledge_mastery
for select to authenticated using (private.can_access_student(student_id));
create policy knowledge_mastery_insert_owned on public.knowledge_mastery
for insert to authenticated with check (private.can_access_student(student_id));
create policy knowledge_mastery_update_owned on public.knowledge_mastery
for update to authenticated using (private.can_access_student(student_id))
with check (private.can_access_student(student_id));

create policy thinking_skill_evidence_select_owned on public.thinking_skill_evidence
for select to authenticated using (private.can_access_student(student_id));
create policy thinking_skill_evidence_insert_owned on public.thinking_skill_evidence
for insert to authenticated with check (private.can_access_student(student_id));
create policy thinking_skill_evidence_update_owned on public.thinking_skill_evidence
for update to authenticated using (private.can_access_student(student_id))
with check (private.can_access_student(student_id));

-- No authenticated INSERT/UPDATE/DELETE grant or policy on student_access.
-- No authenticated DELETE grant or policy on any student learning table.

commit;
