-- MathAI Staging 001: student ownership
-- Run only in a fresh/approved Supabase Staging project.

begin;

create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
create schema if not exists private;

create table public.learning_students (
  id uuid primary key default extensions.gen_random_uuid(),
  legacy_email text,
  display_name text not null default '',
  active boolean not null default true,
  created_at timestamptz not null default pg_catalog.now(),
  updated_at timestamptz not null default pg_catalog.now()
);

comment on column public.learning_students.legacy_email is
  'Compatibility metadata only; never use email as a relational ownership key.';

create table public.student_access (
  user_id uuid not null references auth.users(id) on delete cascade,
  student_id uuid not null references public.learning_students(id) on delete cascade,
  role text not null default 'owner' check (role in ('owner', 'student', 'guardian')),
  created_at timestamptz not null default pg_catalog.now(),
  primary key (user_id, student_id)
);

-- PostgreSQL index names cannot be schema-qualified in CREATE INDEX; the fully
-- qualified parent table fixes this index in the public schema.
create index student_access_student_idx
  on public.student_access (student_id, user_id);

comment on table public.student_access is
  'Many-to-many authorization map. Clients cannot self-grant access.';

create or replace function private.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = pg_catalog.now();
  return new;
end;
$$;

revoke all on schema private from public;
revoke all on function private.set_updated_at() from public;

create trigger learning_students_set_updated_at
before update on public.learning_students
for each row execute function private.set_updated_at();

alter table public.learning_students enable row level security;
alter table public.student_access enable row level security;

revoke all on public.learning_students from anon;
revoke all on public.student_access from anon;
revoke all on public.learning_students from authenticated;
revoke all on public.student_access from authenticated;

commit;
