-- MathAI Staging 002: diagnostic and mastery persistence

begin;

do $$
begin
  if pg_catalog.to_regclass('public.learning_students') is null then
    raise exception '001_student_ownership.sql must run first';
  end if;
end $$;

create table public.diagnostic_attempts (
  id uuid primary key default extensions.gen_random_uuid(),
  student_id uuid not null references public.learning_students(id) on delete cascade,
  attempt_key uuid not null,
  profile_id text not null,
  source_type text not null default 'diagnostic' check (source_type in ('diagnostic', 'practice')),
  started_at timestamptz,
  completed_at timestamptz not null,
  created_at timestamptz not null default pg_catalog.now(),
  metadata jsonb not null default '{}'::jsonb,
  unique (student_id, attempt_key)
);

create index diagnostic_attempts_student_profile_completed_idx
  on public.diagnostic_attempts (student_id, profile_id, completed_at desc);

create table public.diagnostic_item_results (
  attempt_id uuid not null references public.diagnostic_attempts(id) on delete cascade,
  question_id text not null,
  credit numeric(5,4) not null check (credit between 0 and 1),
  source_type text not null default 'diagnostic' check (source_type in ('diagnostic', 'practice')),
  answer_payload jsonb not null,
  evidence_payload jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default pg_catalog.now(),
  primary key (attempt_id, question_id)
);

create table public.knowledge_mastery (
  student_id uuid not null references public.learning_students(id) on delete cascade,
  profile_id text not null,
  knowledge_id text not null,
  mastery_status text not null check (mastery_status in ('unassessed', 'needs_work', 'learning', 'basic', 'proficient')),
  mastery_score numeric(5,2) not null check (mastery_score between 0 and 100),
  confidence numeric(5,4) not null check (confidence between 0 and 1),
  evidence_count integer not null check (evidence_count >= 0),
  weighted_credit numeric not null,
  last_evidence_at timestamptz,
  updated_at timestamptz not null default pg_catalog.now(),
  metadata jsonb not null default '{}'::jsonb,
  primary key (student_id, profile_id, knowledge_id)
);

create index knowledge_mastery_student_status_idx
  on public.knowledge_mastery (student_id, mastery_status, updated_at desc);

create table public.thinking_skill_evidence (
  student_id uuid not null references public.learning_students(id) on delete cascade,
  profile_id text not null,
  thinking_skill_id text not null,
  score numeric(5,2) not null check (score between 0 and 100),
  confidence numeric(5,4) not null check (confidence between 0 and 1),
  evidence_count integer not null check (evidence_count >= 0),
  last_evidence_at timestamptz,
  updated_at timestamptz not null default pg_catalog.now(),
  metadata jsonb not null default '{}'::jsonb,
  primary key (student_id, profile_id, thinking_skill_id)
);

create index thinking_skill_evidence_student_profile_idx
  on public.thinking_skill_evidence (student_id, profile_id, updated_at desc);

create trigger knowledge_mastery_set_updated_at
before update on public.knowledge_mastery
for each row execute function private.set_updated_at();

create trigger thinking_skill_evidence_set_updated_at
before update on public.thinking_skill_evidence
for each row execute function private.set_updated_at();

alter table public.diagnostic_attempts enable row level security;
alter table public.diagnostic_item_results enable row level security;
alter table public.knowledge_mastery enable row level security;
alter table public.thinking_skill_evidence enable row level security;

revoke all on public.diagnostic_attempts from anon, authenticated;
revoke all on public.diagnostic_item_results from anon, authenticated;
revoke all on public.knowledge_mastery from anon, authenticated;
revoke all on public.thinking_skill_evidence from anon, authenticated;

commit;
