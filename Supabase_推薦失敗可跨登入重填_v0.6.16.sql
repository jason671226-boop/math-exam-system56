-- MathAI v0.6.16
-- 目的：
-- 1. 推薦／優惠驗證失敗後，即使登出、重整、換裝置，仍能回來修改。
-- 2. 舊版 rejected 推薦紀錄不再永久鎖住帳號。
-- 3. 解鎖目前測試帳號 jason6011226@gmail.com，讓它可以繼續測試。
-- 可重複執行。

create table if not exists public.registration_source_retries (
    user_email text primary key,
    source_type text not null default '',
    source_detail text not null default '',
    status text not null default 'retry_allowed',
    updated_at timestamptz not null default now()
);

alter table public.registration_source_retries enable row level security;

create or replace function public.mathai_save_source_retry(
    p_email text,
    p_source_type text,
    p_source_detail text,
    p_status text default 'retry_allowed'
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
begin
    if v_email = '' then
        return false;
    end if;

    insert into public.registration_source_retries (
        user_email,
        source_type,
        source_detail,
        status,
        updated_at
    )
    values (
        v_email,
        trim(coalesce(p_source_type, '')),
        trim(coalesce(p_source_detail, '')),
        coalesce(nullif(trim(p_status), ''), 'retry_allowed'),
        now()
    )
    on conflict (user_email) do update set
        source_type = excluded.source_type,
        source_detail = excluded.source_detail,
        status = excluded.status,
        updated_at = now();

    return true;
end;
$$;

create or replace function public.mathai_get_source_retry(p_email text)
returns table (
    source_type text,
    source_detail text,
    status text
)
language sql
security definer
set search_path = public
as $$
    select
        r.source_type,
        r.source_detail,
        r.status
    from public.registration_source_retries r
    where lower(r.user_email) = lower(trim(coalesce(p_email, '')))
    limit 1;
$$;

create or replace function public.mathai_clear_source_retry(p_email text)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    delete from public.registration_source_retries
    where lower(user_email) = lower(trim(coalesce(p_email, '')));
    return true;
end;
$$;

revoke all on function public.mathai_save_source_retry(text, text, text, text)
from public;
revoke all on function public.mathai_get_source_retry(text)
from public;
revoke all on function public.mathai_clear_source_retry(text)
from public;

grant execute on function public.mathai_save_source_retry(text, text, text, text)
to anon, authenticated;
grant execute on function public.mathai_get_source_retry(text)
to anon, authenticated;
grant execute on function public.mathai_clear_source_retry(text)
to anon, authenticated;

-- 解鎖目前用來測試「推薦失敗後重填」的帳號。
insert into public.registration_source_retries (
    user_email,
    source_type,
    source_detail,
    status,
    updated_at
)
values (
    'jason6011226@gmail.com',
    '親友／老師介紹',
    '',
    'retry_allowed',
    now()
)
on conflict (user_email) do update set
    source_type = '親友／老師介紹',
    status = 'retry_allowed',
    updated_at = now();

-- 舊 v0.6.12 若曾留下 rejected referral，建立可重填狀態。
insert into public.registration_source_retries (
    user_email,
    source_type,
    source_detail,
    status,
    updated_at
)
select
    lower(r.referred_email),
    '親友／老師介紹',
    coalesce(r.referrer_email, ''),
    'retry_allowed',
    now()
from public.referrals r
where lower(coalesce(r.status, '')) = 'rejected'
  and not exists (
      select 1
      from public.referrals ok
      where lower(ok.referred_email) = lower(r.referred_email)
        and lower(coalesce(ok.status, '')) in (
            'pending',
            'processing',
            'awarded',
            'monthly_limit'
        )
  )
on conflict (user_email) do update set
    source_type = excluded.source_type,
    source_detail = excluded.source_detail,
    status = 'retry_allowed',
    updated_at = now();

-- 驗證目前測試帳號已可重填
select *
from public.mathai_get_source_retry('jason6011226@gmail.com');
