-- PROPOSAL ONLY. Do not execute without review, backup, RLS design, and explicit approval.
-- Stable student UUID is the relational identity; email is intentionally not a foreign key.
-- Prerequisite: public.learning_students must exist from the reviewed identity migration.

create extension if not exists pgcrypto;

do $$ begin
  if to_regclass('public.learning_students') is null then
    raise exception 'Missing prerequisite table public.learning_students';
  end if;
end $$;

create table diagnostic_attempts (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references public.learning_students(id) on delete cascade,
  attempt_key uuid not null,
  profile_id text not null,
  source_type text not null default 'diagnostic' check (source_type in ('diagnostic','practice')),
  started_at timestamptz,
  completed_at timestamptz not null,
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  unique (student_id, attempt_key)
);
create index diagnostic_attempts_student_profile_completed_idx on diagnostic_attempts (student_id, profile_id, completed_at desc);

create table diagnostic_item_results (
  attempt_id uuid not null references diagnostic_attempts(id) on delete cascade,
  question_id text not null,
  credit numeric(5,4) not null check (credit between 0 and 1),
  source_type text not null default 'diagnostic' check (source_type in ('diagnostic','practice')),
  answer_payload jsonb not null,
  evidence_payload jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key (attempt_id, question_id)
);

create table knowledge_mastery (
  student_id uuid not null references public.learning_students(id) on delete cascade,
  profile_id text not null,
  knowledge_id text not null,
  mastery_status text not null check (mastery_status in ('unassessed','needs_work','learning','basic','proficient')),
  mastery_score numeric(5,2) not null check (mastery_score between 0 and 100),
  confidence numeric(5,4) not null check (confidence between 0 and 1),
  evidence_count integer not null check (evidence_count >= 0),
  weighted_credit numeric not null,
  last_evidence_at timestamptz,
  updated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  primary key (student_id, profile_id, knowledge_id)
);
create index knowledge_mastery_student_status_idx on knowledge_mastery (student_id, mastery_status, updated_at desc);

create table thinking_skill_evidence (
  student_id uuid not null references public.learning_students(id) on delete cascade,
  profile_id text not null,
  thinking_skill_id text not null,
  score numeric(5,2) not null check (score between 0 and 100),
  confidence numeric(5,4) not null check (confidence between 0 and 1),
  evidence_count integer not null check (evidence_count >= 0),
  last_evidence_at timestamptz,
  updated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  primary key (student_id, profile_id, thinking_skill_id)
);
create index thinking_skill_evidence_student_profile_idx on thinking_skill_evidence (student_id, profile_id, updated_at desc);

-- Deny-by-default posture: tables have RLS enabled but intentionally receive no
-- policies in this proposal. Direct app access remains blocked until the human
-- identity decision is implemented and each policy is reviewed in staging.
alter table public.diagnostic_attempts enable row level security;
alter table public.diagnostic_item_results enable row level security;
alter table public.knowledge_mastery enable row level security;
alter table public.thinking_skill_evidence enable row level security;

-- Upserts use the declared composite primary keys; diagnostic attempt retries use
-- (student_id, attempt_key). Before execution add auth-to-student mapping, updated_at trigger,
-- ownership/RLS policies, retention policy, audit logging, and rollback procedure.
