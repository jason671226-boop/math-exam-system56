-- MathAI v0.6.12
-- 推薦獎勵、優惠碼、來源審核、有效使用紀錄與點數流水
-- 請在 Supabase SQL Editor 執行一次。
-- 本檔可重複執行，不會刪除既有資料。

alter table public.user_profiles
    add column if not exists discovery_source text not null default '',
    add column if not exists source_detail text not null default '',
    add column if not exists source_reward_status text not null default 'none',
    add column if not exists account_status text not null default 'active',
    add column if not exists first_effective_use_at timestamptz;

create table if not exists public.user_activity_events (
    id uuid primary key,
    user_email text not null,
    event_type text not null,
    created_at timestamptz not null default now()
);

create index if not exists user_activity_events_email_created_idx
    on public.user_activity_events (user_email, created_at desc);

create table if not exists public.referrals (
    id bigserial primary key,
    referrer_email text not null,
    referred_email text not null unique,
    status text not null default 'pending',
    reward_points integer not null default 50,
    reason text not null default '',
    created_at timestamptz not null default now(),
    awarded_at timestamptz,
    updated_at timestamptz not null default now(),
    constraint referrals_different_accounts
        check (lower(referrer_email) <> lower(referred_email))
);

create index if not exists referrals_referrer_status_idx
    on public.referrals (referrer_email, status, awarded_at desc);

create table if not exists public.promo_codes (
    code text primary key,
    points integer not null default 50 check (points > 0),
    active boolean not null default true,
    max_uses integer not null default 0 check (max_uses >= 0),
    usage_count integer not null default 0 check (usage_count >= 0),
    expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.promo_redemptions (
    id bigserial primary key,
    code text not null references public.promo_codes(code),
    user_email text not null unique,
    points integer not null default 50,
    status text not null default 'awarded',
    created_at timestamptz not null default now(),
    unique (code, user_email)
);

create table if not exists public.acquisition_claims (
    id bigserial primary key,
    user_email text not null unique,
    source_type text not null,
    source_detail text not null,
    status text not null default 'pending',
    reward_points integer not null default 50,
    created_at timestamptz not null default now(),
    reviewed_at timestamptz,
    updated_at timestamptz not null default now()
);

create table if not exists public.credit_transactions (
    id uuid primary key,
    user_email text not null,
    points integer not null,
    reason text not null,
    reference_type text not null default '',
    reference_id text not null default '',
    created_at timestamptz not null default now()
);

create index if not exists credit_transactions_email_created_idx
    on public.credit_transactions (user_email, created_at desc);

-- 讓既有會員保留正常狀態。
update public.user_profiles
set account_status = 'active'
where account_status is null or account_status = '';

-- 執行後可用這些查詢確認資料表已建立。
select
    table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
      'user_activity_events',
      'referrals',
      'promo_codes',
      'promo_redemptions',
      'acquisition_claims',
      'credit_transactions'
  )
order by table_name;
