-- MathAI Staging 008: Teacher Feedback human evidence layer.
-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.
-- This table is independent from diagnostic, knowledge, and thinking evidence.

begin;

alter table public.student_access
  drop constraint if exists student_access_role_check;
alter table public.student_access
  add constraint student_access_role_check
  check (role in ('owner', 'student', 'guardian', 'teacher'));

create table if not exists public.teacher_feedback (
  id uuid primary key default extensions.gen_random_uuid(),
  student_id uuid not null references public.learning_students(id) on delete cascade,
  recorded_by uuid not null references auth.users(id) on delete restrict,
  profile_id text not null,
  scope_type text not null check (scope_type in ('overall', 'knowledge', 'thinking_skill')),
  feedback_text text not null check (
    pg_catalog.length(pg_catalog.btrim(feedback_text)) between 1 and 2000
  ),
  recommendation text check (
    recommendation is null or pg_catalog.length(pg_catalog.btrim(recommendation)) <= 1000
  ),
  knowledge_point_id text,
  thinking_skill_id text,
  created_at timestamptz not null default pg_catalog.now(),
  constraint teacher_feedback_scope_mapping_check check (
    (scope_type = 'overall' and knowledge_point_id is null and thinking_skill_id is null)
    or (scope_type = 'knowledge' and knowledge_point_id is not null and thinking_skill_id is null)
    or (scope_type = 'thinking_skill' and knowledge_point_id is null and thinking_skill_id is not null)
  )
);

create index if not exists teacher_feedback_student_created_idx
  on public.teacher_feedback (student_id, created_at desc);
create index if not exists teacher_feedback_recorded_by_idx
  on public.teacher_feedback (recorded_by, created_at desc);

alter table public.teacher_feedback enable row level security;
revoke all on public.teacher_feedback from anon, authenticated;
grant select, insert, delete on public.teacher_feedback to authenticated;

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

drop policy if exists teacher_feedback_select_authorized
  on public.teacher_feedback;
create policy teacher_feedback_select_authorized
on public.teacher_feedback
for select to authenticated
using (private.can_access_student(student_id));

drop policy if exists teacher_feedback_insert_teacher
  on public.teacher_feedback;
create policy teacher_feedback_insert_teacher
on public.teacher_feedback
for insert to authenticated
with check (
  recorded_by = (select auth.uid())
  and exists (
    select 1
    from public.teacher_access as access
    where access.teacher_id = (select auth.uid())
      and access.student_id = teacher_feedback.student_id
  )
);

drop policy if exists teacher_feedback_delete_staging_smoke_teacher
  on public.teacher_feedback;
create policy teacher_feedback_delete_staging_smoke_teacher
on public.teacher_feedback
for delete to authenticated
using (
  profile_id = 'STAGING_SMOKE'
  and recorded_by = (select auth.uid())
);

-- Synthetic users are teachers only of their own reserved Staging students.
insert into public.teacher_access (teacher_id, student_id)
select auth_user.id, mapping.student_id
from auth.users as auth_user
join (values
  ('student-a-staging@example.com', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid),
  ('student-b-staging@example.com', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'::uuid)
) as mapping(email, student_id)
  on pg_catalog.lower(auth_user.email) = mapping.email
on conflict (teacher_id, student_id) do nothing;

-- Feedback is otherwise immutable to authenticated clients in v1: no UPDATE grant.
-- Teacher assignments remain admin-controlled; clients receive no write grant.

commit;
