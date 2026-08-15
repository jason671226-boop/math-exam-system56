-- MathAI v0.6.14
-- 目的：
-- 1. 新增「管理員指定合格推薦人」欄位。
-- 2. 將 jason671226@gmail.com 設定為合格推薦人。
-- 可重複執行。

alter table public.student_profile_controls
    add column if not exists referral_eligible_override boolean
    not null default false;

insert into public.student_profile_controls (
    email,
    referral_eligible_override,
    updated_at
)
values (
    'jason671226@gmail.com',
    true,
    now()
)
on conflict (email) do update set
    referral_eligible_override = true,
    updated_at = now();

select
    email,
    referral_eligible_override,
    locked_last_name,
    locked_first_name,
    school,
    grade,
    version
from public.student_profile_controls
where lower(email) = 'jason671226@gmail.com';
