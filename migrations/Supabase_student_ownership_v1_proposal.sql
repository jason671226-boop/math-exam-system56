-- PROPOSAL ONLY. FIRST STEP OF THE APPROVED STAGING SEQUENCE.
-- Supabase Auth identity and stable student identity are intentionally distinct.

create extension if not exists pgcrypto;

create table public.learning_students (
  id uuid primary key default gen_random_uuid(),
  legacy_email text,
  display_name text not null default '',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on column public.learning_students.legacy_email is
  'Compatibility metadata only; never use email as a relational ownership key.';

create table public.student_access (
  user_id uuid not null references auth.users(id) on delete cascade,
  student_id uuid not null references public.learning_students(id) on delete cascade,
  role text not null default 'owner' check (role in ('owner', 'student', 'guardian')),
  created_at timestamptz not null default now(),
  primary key (user_id, student_id)
);

create index student_access_student_idx on public.student_access (student_id, user_id);

comment on table public.student_access is
  'Many-to-many authorization map. Private Beta provisions owner rows; clients cannot self-grant access.';

alter table public.learning_students enable row level security;
alter table public.student_access enable row level security;

-- No permissive policies here. Ownership rows are provisioned only through the
-- approved staging bootstrap. The RLS proposal adds current-user SELECT only.
