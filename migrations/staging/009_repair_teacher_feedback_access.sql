-- MathAI Staging 009: complete teacher assignment and smoke cleanup support.
-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.

begin;

alter table public.teacher_feedback
  add column if not exists profile_id text;
update public.teacher_feedback
set profile_id = 'LEGACY_PRE_009'
where profile_id is null;
alter table public.teacher_feedback
  alter column profile_id set not null;

create table if not exists public.teacher_access (
  teacher_id uuid not null references auth.users(id) on delete cascade,
  student_id uuid not null references public.learning_students(id) on delete cascade,
  created_at timestamptz not null default pg_catalog.now(),
  primary key (teacher_id, student_id)
);
create index if not exists teacher_access_student_idx
  on public.teacher_access (student_id, teacher_id);
alter table public.teacher_access enable row level security;
revoke all on public.teacher_access from anon, authenticated;
grant select on public.teacher_access to authenticated;

drop policy if exists teacher_access_select_own on public.teacher_access;
create policy teacher_access_select_own on public.teacher_access
for select to authenticated
using (teacher_id = (select auth.uid()));

drop policy if exists teacher_feedback_insert_teacher
  on public.teacher_feedback;
create policy teacher_feedback_insert_teacher
on public.teacher_feedback
for insert to authenticated
with check (
  recorded_by = (select auth.uid())
  and exists (
    select 1 from public.teacher_access as access
    where access.teacher_id = (select auth.uid())
      and access.student_id = teacher_feedback.student_id
  )
);

grant delete on public.teacher_feedback to authenticated;
drop policy if exists teacher_feedback_delete_staging_smoke_teacher
  on public.teacher_feedback;
create policy teacher_feedback_delete_staging_smoke_teacher
on public.teacher_feedback
for delete to authenticated
using (
  profile_id = 'STAGING_SMOKE'
  and recorded_by = (select auth.uid())
);

insert into public.teacher_access (teacher_id, student_id)
select auth_user.id, mapping.student_id
from auth.users as auth_user
join (values
  ('student-a-staging@example.com', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid),
  ('student-b-staging@example.com', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'::uuid)
) as mapping(email, student_id)
  on pg_catalog.lower(auth_user.email) = mapping.email
on conflict (teacher_id, student_id) do nothing;

commit;
