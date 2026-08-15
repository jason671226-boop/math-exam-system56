-- PROPOSAL ONLY
-- DO NOT RUN ON PRODUCTION
-- MathAI v0.8.0 Private-School Learning Map Pilot
-- Phase 1.1: data-model proposal only; no application code executes this file.
--
-- IMPORTANT SECURITY NOTE:
-- Staging ownership is Supabase Auth plus the many-to-many student_access map.
-- The current custom OTP runtime must not write these tables until it establishes
-- a real Supabase Auth session (`auth.uid()`). Do not expose anonymous CRUD and do
-- not substitute a service-role key as the student authorization boundary.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- A. Stable student identity for the new learning model
-- ---------------------------------------------------------------------------
create table if not exists public.learning_students (
    id uuid primary key default gen_random_uuid(),
    legacy_email text,
    display_name text not null default '',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists learning_students_legacy_email_unique_idx
    on public.learning_students (lower(legacy_email))
    where legacy_email is not null and trim(legacy_email) <> '';

comment on column public.learning_students.legacy_email is
    'Compatibility lookup only; new learning records should reference learning_students.id.';

-- The focused Private Beta ownership map is defined in
-- Supabase_student_ownership_v1_proposal.sql. Do not use this legacy broad
-- pilot proposal as the staging persistence migration sequence.

-- ---------------------------------------------------------------------------
-- B. Knowledge Map / Thinking Skill catalogs
-- ---------------------------------------------------------------------------
create table if not exists public.knowledge_points (
    id text primary key,
    grade smallint not null check (grade in (5, 6)),
    domain text not null,
    ability_tags jsonb not null default '[]'::jsonb,
    main_unit text not null,
    sub_unit text not null,
    learning_focus text not null,
    question_types jsonb not null default '[]'::jsonb,
    curriculum_codes jsonb not null default '[]'::jsonb,
    description text not null default '',
    official_mapping_status text not null default 'pending_verification',
    private_school_weight_status text not null default 'not_assigned',
    sort_order integer not null default 0,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (id ~ '^G[56]-K[0-9]{3}$')
);

create table if not exists public.publisher_unit_mappings (
    id uuid primary key default gen_random_uuid(),
    knowledge_point_id text not null references public.knowledge_points(id) on delete cascade,
    publisher text not null,
    grade smallint not null check (grade in (5, 6)),
    semester text not null default '',
    main_unit text not null default '',
    sub_unit text not null default '',
    section text not null default '',
    source_note text not null default '',
    created_at timestamptz not null default now()
);

create unique index if not exists publisher_unit_mappings_unique_idx
    on public.publisher_unit_mappings (
        knowledge_point_id, publisher, grade, semester, main_unit, sub_unit, section
    );

create table if not exists public.thinking_skills (
    id text primary key,
    name text not null,
    category text not null,
    description text not null,
    min_grade smallint not null default 5 check (min_grade between 1 and 12),
    max_grade smallint not null default 9 check (max_grade between 1 and 12),
    check (min_grade <= max_grade),
    sort_order integer not null default 0,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (id ~ '^TS-[A-Z0-9][A-Z0-9_-]*$')
);

-- Question ID type in the existing item_bank has not been verified in this
-- Phase 1.1 also records whether each Thinking Skill is primary (mainly assessed)
-- or supporting (used during the solution). Primary mappings should normally
-- carry greater diagnostic weight.
-- repository. Use question_ref text in the proposal so no unsafe FK assumption
-- is made. After staging schema inspection, this can be migrated to a concrete FK.
create table if not exists public.question_knowledge_links (
    source_type text not null default 'item_bank',
    question_ref text not null,
    knowledge_point_id text not null references public.knowledge_points(id) on delete cascade,
    weight numeric not null default 1 check (weight > 0),
    created_at timestamptz not null default now(),
    primary key (source_type, question_ref, knowledge_point_id)
);

create table if not exists public.question_thinking_links (
    source_type text not null default 'item_bank',
    question_ref text not null,
    thinking_skill_id text not null references public.thinking_skills(id) on delete cascade,
    skill_role text not null default 'supporting' check (skill_role in ('primary', 'supporting')),
    weight numeric not null default 1 check (weight > 0),
    created_at timestamptz not null default now(),
    primary key (source_type, question_ref, thinking_skill_id)
);

-- Optional default relationship between curriculum nodes and frequently useful
-- thinking tools. Question-level links remain the primary evidence source.
create table if not exists public.knowledge_thinking_links (
    knowledge_point_id text not null references public.knowledge_points(id) on delete cascade,
    thinking_skill_id text not null references public.thinking_skills(id) on delete cascade,
    relation_type text not null default 'suggested',
    weight numeric not null default 1 check (weight > 0),
    created_at timestamptz not null default now(),
    primary key (knowledge_point_id, thinking_skill_id, relation_type)
);

-- ---------------------------------------------------------------------------
-- C. Mastery state + evidence events
-- ---------------------------------------------------------------------------
create table if not exists public.student_mastery_states (
    student_id uuid not null references public.learning_students(id) on delete cascade,
    target_type text not null check (target_type in ('knowledge_point', 'thinking_skill')),
    target_id text not null,
    status text not null default 'unassessed'
        check (status in ('unassessed', 'needs_work', 'learning', 'basic', 'proficient')),
    score_numeric numeric not null default 0 check (score_numeric between 0 and 100),
    confidence numeric not null default 0 check (confidence between 0 and 1),
    evidence_count integer not null default 0 check (evidence_count >= 0),
    last_assessed_at timestamptz,
    next_review_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    primary key (student_id, target_type, target_id)
);

create index if not exists student_mastery_states_review_idx
    on public.student_mastery_states (student_id, next_review_at);

create table if not exists public.mastery_evidence_events (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references public.learning_students(id) on delete cascade,
    target_type text not null check (target_type in ('knowledge_point', 'thinking_skill')),
    target_id text not null,
    source_type text not null check (
        source_type in ('diagnostic', 'practice', 'teacher_feedback', 'integrated_exam', 'system')
    ),
    source_ref text not null default '',
    is_correct boolean,
    difficulty text not null default 'standard'
        check (difficulty in ('basic', 'standard', 'advanced')),
    hints_used integer not null default 0 check (hints_used >= 0),
    attempts integer not null default 1 check (attempts >= 1),
    weight numeric not null default 1 check (weight > 0),
    payload jsonb not null default '{}'::jsonb,
    occurred_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create index if not exists mastery_evidence_student_target_idx
    on public.mastery_evidence_events (student_id, target_type, target_id, occurred_at desc);

-- ---------------------------------------------------------------------------
-- D. Teacher feedback skeleton (no teacher-login system in Phase 1)
-- ---------------------------------------------------------------------------
create table if not exists public.teacher_feedback_sessions (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references public.learning_students(id) on delete cascade,
    recorded_by text not null default '',
    teacher_id uuid,
    teacher_name text not null default '',
    understanding_level text not null default '',
    needed_hints boolean,
    common_errors jsonb not null default '[]'::jsonb,
    student_reaction text not null default '',
    ready_to_advance boolean not null default false,
    note text not null default '',
    created_at timestamptz not null default now()
);

create table if not exists public.teacher_feedback_knowledge_links (
    feedback_session_id uuid not null references public.teacher_feedback_sessions(id) on delete cascade,
    knowledge_point_id text not null references public.knowledge_points(id) on delete cascade,
    primary key (feedback_session_id, knowledge_point_id)
);

create table if not exists public.teacher_feedback_thinking_links (
    feedback_session_id uuid not null references public.teacher_feedback_sessions(id) on delete cascade,
    thinking_skill_id text not null references public.thinking_skills(id) on delete cascade,
    primary key (feedback_session_id, thinking_skill_id)
);

-- ---------------------------------------------------------------------------
-- E. Target-school profile skeleton only (no real school claims in Phase 1)
-- ---------------------------------------------------------------------------
create table if not exists public.target_schools (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    city text not null default '',
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.school_exam_profiles (
    id uuid primary key default gen_random_uuid(),
    target_school_id uuid not null references public.target_schools(id) on delete cascade,
    exam_year integer,
    exam_format text not null default '',
    exam_duration_min integer,
    notes text not null default '',
    status text not null default 'draft',
    created_at timestamptz not null default now()
);

create table if not exists public.school_exam_topic_weights (
    profile_id uuid not null references public.school_exam_profiles(id) on delete cascade,
    knowledge_point_id text not null references public.knowledge_points(id) on delete cascade,
    weight numeric not null default 1 check (weight >= 0),
    difficulty_hint text not null default '',
    evidence_note text not null default '',
    primary key (profile_id, knowledge_point_id)
);

create table if not exists public.student_exam_targets (
    student_id uuid not null references public.learning_students(id) on delete cascade,
    target_school_id uuid not null references public.target_schools(id) on delete cascade,
    target_exam_date date,
    priority integer not null default 1,
    created_at timestamptz not null default now(),
    primary key (student_id, target_school_id)
);

-- ---------------------------------------------------------------------------
-- F. RLS posture for proposal
-- ---------------------------------------------------------------------------
alter table public.learning_students enable row level security;
alter table public.student_mastery_states enable row level security;
alter table public.mastery_evidence_events enable row level security;
alter table public.teacher_feedback_sessions enable row level security;
alter table public.teacher_feedback_knowledge_links enable row level security;
alter table public.teacher_feedback_thinking_links enable row level security;
alter table public.student_exam_targets enable row level security;

-- Shared catalog tables may eventually be readable to app users, but this
-- proposal intentionally does not grant permissions because the current custom
-- OTP identity flow is not tied to auth.uid(). Validate the access path in staging
-- before adding any policy or GRANT.

-- ---------------------------------------------------------------------------
-- G. Explicitly NOT included in Phase 1
-- ---------------------------------------------------------------------------
-- * No DROP TABLE / destructive ALTER
-- * No changes to student_profile_controls, member_wallets, ledger or referral RPCs
-- * No parent_report_snapshots table; parent reports should aggregate live sources first
-- * No direct anonymous CRUD policies
-- * No execution instructions for production
