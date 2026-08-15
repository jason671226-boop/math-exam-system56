create table if not exists public.student_profile_controls (
    email text primary key,
    identity_locked boolean not null default false,
    locked_last_name text not null default '',
    locked_first_name text not null default '',
    grade text not null default '',
    version text not null default '',
    change_year integer not null default extract(year from now())::integer,
    change_count integer not null default 0,
    referral_eligible_override boolean not null default false,
    updated_at timestamptz not null default now()
);

alter table public.student_profile_controls enable row level security;


alter table public.student_profile_controls
    add column if not exists referral_eligible_override boolean
    not null default false;
