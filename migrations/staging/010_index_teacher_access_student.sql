-- MathAI Staging 010: cover teacher_access student FK and RLS lookup.
-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.

begin;

create index if not exists teacher_access_student_idx
  on public.teacher_access (student_id, teacher_id);

commit;
