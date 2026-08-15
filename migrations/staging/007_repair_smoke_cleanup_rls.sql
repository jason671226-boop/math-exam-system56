-- MathAI Staging 007: repair synthetic smoke cleanup grants and policies.
-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.
-- Authenticated owners may delete only rows whose profile_id is STAGING_SMOKE.

begin;

do $$
declare
  smoke_auth_user_count integer;
begin
  select pg_catalog.count(*) into smoke_auth_user_count
  from auth.users as auth_user
  where pg_catalog.lower(auth_user.email) in (
    'student-a-staging@example.com',
    'student-b-staging@example.com'
  );

  if smoke_auth_user_count <> 2 then
    raise exception using message =
      'STAGING ONLY: both synthetic Auth users must exist before applying 007';
  end if;
end $$;

grant delete on public.diagnostic_attempts to authenticated;
grant delete on public.knowledge_mastery to authenticated;
grant delete on public.thinking_skill_evidence to authenticated;

drop policy if exists diagnostic_attempts_delete_staging_smoke_owned
  on public.diagnostic_attempts;
create policy diagnostic_attempts_delete_staging_smoke_owned
on public.diagnostic_attempts
for delete to authenticated
using (
  private.can_access_student(student_id)
  and profile_id = 'STAGING_SMOKE'
);

drop policy if exists knowledge_mastery_delete_staging_smoke_owned
  on public.knowledge_mastery;
create policy knowledge_mastery_delete_staging_smoke_owned
on public.knowledge_mastery
for delete to authenticated
using (
  private.can_access_student(student_id)
  and profile_id = 'STAGING_SMOKE'
);

drop policy if exists thinking_skill_evidence_delete_staging_smoke_owned
  on public.thinking_skill_evidence;
create policy thinking_skill_evidence_delete_staging_smoke_owned
on public.thinking_skill_evidence
for delete to authenticated
using (
  private.can_access_student(student_id)
  and profile_id = 'STAGING_SMOKE'
);

-- diagnostic_item_results are removed only by the attempt FK cascade.
-- No DELETE is granted on student_access or learning_students.

commit;
