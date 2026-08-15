-- MathAI v0.6.9
-- 補齊完整會員資料欄位。
-- 可以重複執行，已存在的欄位不會重建。

create table if not exists public.user_profiles (
    email text primary key,
    last_name text not null default '',
    first_name text not null default '',
    city text not null default '',
    district text not null default '',
    school text not null default '',
    grade text not null default '',
    version text not null default '',
    traits jsonb not null default '[]'::jsonb,
    interests jsonb not null default '[]'::jsonb,
    credits integer not null default 15,
    updated_at timestamptz not null default now()
);

alter table public.user_profiles
    add column if not exists last_name text not null default '',
    add column if not exists first_name text not null default '',
    add column if not exists city text not null default '',
    add column if not exists district text not null default '',
    add column if not exists school text not null default '',
    add column if not exists grade text not null default '',
    add column if not exists version text not null default '',
    add column if not exists traits jsonb not null default '[]'::jsonb,
    add column if not exists interests jsonb not null default '[]'::jsonb,
    add column if not exists credits integer not null default 15,
    add column if not exists updated_at timestamptz not null default now();

create unique index if not exists user_profiles_email_unique_idx
    on public.user_profiles (email);

alter table public.student_profile_controls
    add column if not exists city text not null default '',
    add column if not exists district text not null default '',
    add column if not exists school text not null default '',
    add column if not exists traits jsonb not null default '[]'::jsonb,
    add column if not exists interests jsonb not null default '[]'::jsonb,
    add column if not exists credits integer;

-- 把帳號控制表中已存在的姓名、年級、版本補到 user_profiles。
insert into public.user_profiles (
    email,
    last_name,
    first_name,
    grade,
    version,
    credits,
    updated_at
)
select
    email,
    locked_last_name,
    locked_first_name,
    grade,
    version,
    coalesce(credits, 15),
    now()
from public.student_profile_controls
where email is not null and email <> ''
on conflict (email) do update set
    last_name = case
        when excluded.last_name <> '' then excluded.last_name
        else public.user_profiles.last_name
    end,
    first_name = case
        when excluded.first_name <> '' then excluded.first_name
        else public.user_profiles.first_name
    end,
    grade = case
        when excluded.grade <> '' then excluded.grade
        else public.user_profiles.grade
    end,
    version = case
        when excluded.version <> '' then excluded.version
        else public.user_profiles.version
    end,
    credits = coalesce(excluded.credits, public.user_profiles.credits),
    updated_at = now();

select
    email,
    last_name,
    first_name,
    city,
    district,
    school,
    grade,
    version,
    traits,
    interests,
    credits
from public.user_profiles
order by updated_at desc
limit 20;
