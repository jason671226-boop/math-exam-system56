-- =========================================================
-- MathAI v0.7.0｜資料架構整理
-- =========================================================
-- 目標：
-- 1. student_profile_controls = 唯一會員主檔
-- 2. member_wallets = 唯一正式點數來源
-- 3. referrals / user_activity_events = 推薦與有效使用紀錄
-- 4. Session / user_profiles 不再反向覆蓋正式資料
--
-- 本檔可重複執行，不會刪除既有會員、錢包或推薦資料。
-- user_profiles 保留作歷史資料，不再由 v0.7.0 App 使用。
-- =========================================================

-- ---------------------------------------------------------
-- A. 唯一會員主檔：student_profile_controls
-- ---------------------------------------------------------
create table if not exists public.student_profile_controls (
    email text primary key,
    identity_locked boolean not null default false,
    locked_last_name text not null default '',
    locked_first_name text not null default '',
    city text not null default '',
    district text not null default '',
    school text not null default '',
    grade text not null default '',
    version text not null default '',
    traits jsonb not null default '[]'::jsonb,
    interests jsonb not null default '[]'::jsonb,
    discovery_source text not null default '',
    source_detail text not null default '',
    source_reward_status text not null default 'none',
    referral_eligible_override boolean not null default false,
    change_year integer not null default extract(year from now())::integer,
    change_count integer not null default 0,
    credits integer,
    updated_at timestamptz not null default now()
);

alter table public.student_profile_controls
    add column if not exists city text not null default '',
    add column if not exists district text not null default '',
    add column if not exists school text not null default '',
    add column if not exists grade text not null default '',
    add column if not exists version text not null default '',
    add column if not exists traits jsonb not null default '[]'::jsonb,
    add column if not exists interests jsonb not null default '[]'::jsonb,
    add column if not exists discovery_source text not null default '',
    add column if not exists source_detail text not null default '',
    add column if not exists source_reward_status text not null default 'none',
    add column if not exists referral_eligible_override boolean not null default false,
    add column if not exists change_year integer not null default extract(year from now())::integer,
    add column if not exists change_count integer not null default 0,
    add column if not exists credits integer,
    add column if not exists updated_at timestamptz not null default now();

alter table public.student_profile_controls enable row level security;

-- 舊 user_profiles 若結構完整，盡量把資料搬到唯一會員主檔。
-- 若舊表欄位不一致，僅略過搬移，不中斷整份 SQL。
do $$
begin
    if to_regclass('public.user_profiles') is not null then
        begin
            execute $migrate$
                insert into public.student_profile_controls (
                    email,
                    identity_locked,
                    locked_last_name,
                    locked_first_name,
                    city,
                    district,
                    school,
                    grade,
                    version,
                    traits,
                    interests,
                    discovery_source,
                    source_detail,
                    source_reward_status,
                    updated_at
                )
                select
                    lower(trim(email)),
                    (trim(coalesce(last_name, '')) <> ''
                     and trim(coalesce(first_name, '')) <> ''),
                    coalesce(last_name, ''),
                    coalesce(first_name, ''),
                    coalesce(city, ''),
                    coalesce(district, ''),
                    coalesce(school, ''),
                    coalesce(grade, ''),
                    coalesce(version, ''),
                    coalesce(traits, '[]'::jsonb),
                    coalesce(interests, '[]'::jsonb),
                    coalesce(discovery_source, ''),
                    coalesce(source_detail, ''),
                    coalesce(source_reward_status, 'none'),
                    now()
                from public.user_profiles
                where trim(coalesce(email, '')) <> ''
                on conflict (email) do update set
                    locked_last_name = case
                        when public.student_profile_controls.locked_last_name = ''
                        then excluded.locked_last_name
                        else public.student_profile_controls.locked_last_name
                    end,
                    locked_first_name = case
                        when public.student_profile_controls.locked_first_name = ''
                        then excluded.locked_first_name
                        else public.student_profile_controls.locked_first_name
                    end,
                    city = case
                        when public.student_profile_controls.city = ''
                        then excluded.city
                        else public.student_profile_controls.city
                    end,
                    district = case
                        when public.student_profile_controls.district = ''
                        then excluded.district
                        else public.student_profile_controls.district
                    end,
                    school = case
                        when public.student_profile_controls.school = ''
                        then excluded.school
                        else public.student_profile_controls.school
                    end,
                    grade = case
                        when public.student_profile_controls.grade = ''
                        then excluded.grade
                        else public.student_profile_controls.grade
                    end,
                    version = case
                        when public.student_profile_controls.version = ''
                        then excluded.version
                        else public.student_profile_controls.version
                    end,
                    traits = case
                        when public.student_profile_controls.traits = '[]'::jsonb
                        then excluded.traits
                        else public.student_profile_controls.traits
                    end,
                    interests = case
                        when public.student_profile_controls.interests = '[]'::jsonb
                        then excluded.interests
                        else public.student_profile_controls.interests
                    end,
                    discovery_source = case
                        when public.student_profile_controls.discovery_source = ''
                        then excluded.discovery_source
                        else public.student_profile_controls.discovery_source
                    end,
                    source_detail = case
                        when public.student_profile_controls.source_detail = ''
                        then excluded.source_detail
                        else public.student_profile_controls.source_detail
                    end,
                    source_reward_status = case
                        when public.student_profile_controls.source_reward_status in ('', 'none')
                        then excluded.source_reward_status
                        else public.student_profile_controls.source_reward_status
                    end,
                    updated_at = now()
            $migrate$;
        exception when others then
            raise notice 'user_profiles 舊資料搬移略過：%', sqlerrm;
        end;
    end if;
end $$;

-- ---------------------------------------------------------
-- B. 唯一正式點數來源：member_wallets
-- ---------------------------------------------------------
create table if not exists public.member_wallets (
    email text primary key,
    credits integer not null default 100 check (credits >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.member_credit_ledger (
    id uuid primary key,
    user_email text not null,
    delta integer not null,
    balance_after integer not null,
    reason text not null default '',
    reference_type text not null default '',
    reference_id text not null default '',
    created_at timestamptz not null default now()
);

create index if not exists member_credit_ledger_email_created_idx
    on public.member_credit_ledger (user_email, created_at desc);

create table if not exists public.pending_wallet_credits (
    email text primary key,
    pending_points integer not null default 0,
    reason text not null default '',
    updated_at timestamptz not null default now()
);

alter table public.member_wallets enable row level security;
alter table public.member_credit_ledger enable row level security;
alter table public.pending_wallet_credits enable row level security;

-- 只在錢包尚不存在時，從舊會員主檔的 legacy credits 搬一次。
-- 已存在的 wallet（例如 135 / 150）完全不會被覆蓋。
insert into public.member_wallets (
    email,
    credits,
    created_at,
    updated_at
)
select
    lower(trim(c.email)),
    greatest(coalesce(c.credits, 100), 0),
    now(),
    now()
from public.student_profile_controls c
where trim(coalesce(c.email, '')) <> ''
on conflict (email) do nothing;

-- ---------------------------------------------------------
-- C. 推薦、有效使用、儲值與來源獎勵必要表
-- ---------------------------------------------------------
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
    updated_at timestamptz not null default now()
);

alter table public.referrals
    add column if not exists reward_points integer not null default 50,
    add column if not exists reason text not null default '',
    add column if not exists awarded_at timestamptz,
    add column if not exists updated_at timestamptz not null default now();

create unique index if not exists referrals_referred_email_unique_idx
    on public.referrals (referred_email);

create index if not exists referrals_referrer_status_idx
    on public.referrals (referrer_email, status, awarded_at desc);

create table if not exists public.topup_requests (
    id text primary key,
    user_email text not null,
    amount numeric not null default 0,
    points integer not null default 0,
    status text not null default 'pending',
    created_at timestamptz not null default now()
);

create table if not exists public.promo_codes (
    code text primary key,
    points integer not null default 50,
    active boolean not null default true,
    max_uses integer not null default 0,
    usage_count integer not null default 0,
    expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.promo_redemptions (
    id bigserial primary key,
    code text not null,
    user_email text not null,
    points integer not null default 50,
    status text not null default 'awarded',
    created_at timestamptz not null default now()
);

create unique index if not exists promo_redemptions_user_unique_idx
    on public.promo_redemptions (user_email);

create table if not exists public.acquisition_claims (
    id bigserial primary key,
    user_email text not null,
    source_type text not null,
    source_detail text not null,
    status text not null default 'pending',
    reward_points integer not null default 50,
    created_at timestamptz not null default now(),
    reviewed_at timestamptz,
    updated_at timestamptz not null default now()
);

create unique index if not exists acquisition_claims_user_unique_idx
    on public.acquisition_claims (user_email);

create table if not exists public.registration_source_retries (
    user_email text primary key,
    source_type text not null default '',
    source_detail text not null default '',
    status text not null default 'retry_allowed',
    updated_at timestamptz not null default now()
);

alter table public.registration_source_retries enable row level security;

-- ---------------------------------------------------------
-- D. Canonical Profile RPC
-- ---------------------------------------------------------
create or replace function public.mathai_profile_get_v070(p_email text)
returns table (
    found boolean,
    email text,
    identity_locked boolean,
    locked_last_name text,
    locked_first_name text,
    city text,
    district text,
    school text,
    grade text,
    version text,
    traits jsonb,
    interests jsonb,
    discovery_source text,
    source_detail text,
    source_reward_status text,
    referral_eligible_override boolean,
    change_year integer,
    change_count integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
begin
    if v_email = '' then
        return query
        select
            false, ''::text, false, ''::text, ''::text,
            ''::text, ''::text, ''::text, ''::text, ''::text,
            '[]'::jsonb, '[]'::jsonb,
            ''::text, ''::text, 'none'::text,
            false, extract(year from now())::integer, 0;
        return;
    end if;

    if exists(
        select 1
        from public.student_profile_controls p
        where lower(p.email) = v_email
    ) then
        return query
        select
            true,
            lower(p.email),
            p.identity_locked,
            p.locked_last_name,
            p.locked_first_name,
            p.city,
            p.district,
            p.school,
            p.grade,
            p.version,
            coalesce(p.traits, '[]'::jsonb),
            coalesce(p.interests, '[]'::jsonb),
            p.discovery_source,
            p.source_detail,
            p.source_reward_status,
            p.referral_eligible_override,
            p.change_year,
            p.change_count
        from public.student_profile_controls p
        where lower(p.email) = v_email
        limit 1;
        return;
    end if;

    return query
    select
        false, v_email, false, ''::text, ''::text,
        ''::text, ''::text, ''::text, ''::text, ''::text,
        '[]'::jsonb, '[]'::jsonb,
        ''::text, ''::text, 'none'::text,
        false, extract(year from now())::integer, 0;
end;
$$;

create or replace function public.mathai_profile_save_v070(
    p_email text,
    p_identity_locked boolean,
    p_locked_last_name text,
    p_locked_first_name text,
    p_city text,
    p_district text,
    p_school text,
    p_grade text,
    p_version text,
    p_traits jsonb,
    p_interests jsonb,
    p_discovery_source text,
    p_source_detail text,
    p_source_reward_status text,
    p_referral_eligible_override boolean,
    p_change_year integer,
    p_change_count integer
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

    insert into public.student_profile_controls (
        email,
        identity_locked,
        locked_last_name,
        locked_first_name,
        city,
        district,
        school,
        grade,
        version,
        traits,
        interests,
        discovery_source,
        source_detail,
        source_reward_status,
        referral_eligible_override,
        change_year,
        change_count,
        updated_at
    )
    values (
        v_email,
        coalesce(p_identity_locked, false),
        trim(coalesce(p_locked_last_name, '')),
        trim(coalesce(p_locked_first_name, '')),
        trim(coalesce(p_city, '')),
        trim(coalesce(p_district, '')),
        trim(coalesce(p_school, '')),
        trim(coalesce(p_grade, '')),
        trim(coalesce(p_version, '')),
        coalesce(p_traits, '[]'::jsonb),
        coalesce(p_interests, '[]'::jsonb),
        trim(coalesce(p_discovery_source, '')),
        trim(coalesce(p_source_detail, '')),
        coalesce(nullif(trim(p_source_reward_status), ''), 'none'),
        coalesce(p_referral_eligible_override, false),
        coalesce(p_change_year, extract(year from now())::integer),
        greatest(coalesce(p_change_count, 0), 0),
        now()
    )
    on conflict (email) do update set
        identity_locked = excluded.identity_locked,
        locked_last_name = excluded.locked_last_name,
        locked_first_name = excluded.locked_first_name,
        city = excluded.city,
        district = excluded.district,
        school = excluded.school,
        grade = excluded.grade,
        version = excluded.version,
        traits = excluded.traits,
        interests = excluded.interests,
        discovery_source = excluded.discovery_source,
        source_detail = excluded.source_detail,
        source_reward_status = excluded.source_reward_status,
        referral_eligible_override = excluded.referral_eligible_override,
        change_year = excluded.change_year,
        change_count = excluded.change_count,
        updated_at = now();

    return true;
end;
$$;

-- ---------------------------------------------------------
-- E. Canonical Wallet RPC
-- ---------------------------------------------------------
create or replace function public.mathai_wallet_lookup_v070(p_email text)
returns table (
    found boolean,
    credits integer
)
language sql
security definer
set search_path = public
as $$
    select
        exists(
            select 1
            from public.member_wallets w
            where lower(w.email) = lower(trim(coalesce(p_email, '')))
        ),
        (
            select w.credits
            from public.member_wallets w
            where lower(w.email) = lower(trim(coalesce(p_email, '')))
            limit 1
        );
$$;

create or replace function public.mathai_wallet_bootstrap_v070(
    p_email text,
    p_is_new_account boolean default false
)
returns table (
    credits integer,
    created boolean,
    migration_source text,
    pending_applied integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
    v_exists boolean := false;
    v_legacy integer;
    v_initial integer := 100;
    v_created boolean := false;
    v_source text := 'existing_wallet';
    v_pending integer := 0;
    v_balance integer := 0;
begin
    if v_email = '' then
        return query select 0, false, 'invalid_email'::text, 0;
        return;
    end if;

    select exists(
        select 1 from public.member_wallets w
        where lower(w.email) = v_email
    )
    into v_exists;

    if not v_exists then
        select c.credits
        into v_legacy
        from public.student_profile_controls c
        where lower(c.email) = v_email
        limit 1;

        if v_legacy is not null then
            v_initial := greatest(v_legacy, 0);
            v_source := 'legacy_profile_credits';
        elsif coalesce(p_is_new_account, false) then
            v_initial := 100;
            v_source := 'new_account_100';
        else
            v_initial := 100;
            v_source := 'legacy_default_100';
        end if;

        insert into public.member_wallets (
            email, credits, created_at, updated_at
        )
        values (
            v_email, v_initial, now(), now()
        )
        on conflict (email) do nothing;

        v_created := true;
    end if;

    select coalesce(p.pending_points, 0)
    into v_pending
    from public.pending_wallet_credits p
    where lower(p.email) = v_email
    limit 1;

    v_pending := coalesce(v_pending, 0);

    if v_pending <> 0 then
        update public.member_wallets w
        set
            credits = w.credits + v_pending,
            updated_at = now()
        where lower(w.email) = v_email;

        select w.credits
        into v_balance
        from public.member_wallets w
        where lower(w.email) = v_email
        limit 1;

        insert into public.member_credit_ledger (
            id, user_email, delta, balance_after,
            reason, reference_type, reference_id, created_at
        )
        values (
            gen_random_uuid(), v_email, v_pending, v_balance,
            'pending_wallet_credit_applied',
            'wallet_bootstrap', '', now()
        );

        delete from public.pending_wallet_credits p
        where lower(p.email) = v_email;
    end if;

    select w.credits
    into v_balance
    from public.member_wallets w
    where lower(w.email) = v_email
    limit 1;

    return query
    select
        coalesce(v_balance, 0),
        v_created,
        v_source,
        v_pending;
end;
$$;

create or replace function public.mathai_wallet_adjust_v070(
    p_email text,
    p_delta integer,
    p_reason text default '',
    p_reference_type text default '',
    p_reference_id text default ''
)
returns table (
    success boolean,
    new_balance integer,
    message text
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
    v_delta integer := coalesce(p_delta, 0);
    v_balance integer := 0;
begin
    if v_email = '' or v_delta = 0 then
        return query
        select false, 0, 'Email 或點數異動值不正確。'::text;
        return;
    end if;

    if not exists(
        select 1 from public.member_wallets w
        where lower(w.email) = v_email
    ) then
        select b.credits
        into v_balance
        from public.mathai_wallet_bootstrap_v070(v_email, false) b
        limit 1;
    end if;

    select w.credits
    into v_balance
    from public.member_wallets w
    where lower(w.email) = v_email
    for update;

    if v_balance + v_delta < 0 then
        return query
        select false, v_balance, '點數不足。'::text;
        return;
    end if;

    update public.member_wallets w
    set
        credits = w.credits + v_delta,
        updated_at = now()
    where lower(w.email) = v_email
    returning w.credits into v_balance;

    insert into public.member_credit_ledger (
        id, user_email, delta, balance_after,
        reason, reference_type, reference_id, created_at
    )
    values (
        gen_random_uuid(),
        v_email,
        v_delta,
        v_balance,
        trim(coalesce(p_reason, '')),
        trim(coalesce(p_reference_type, '')),
        trim(coalesce(p_reference_id, '')),
        now()
    );

    return query
    select true, v_balance, '點數異動完成。'::text;
end;
$$;

-- ---------------------------------------------------------
-- F. Referral RPC：完全使用 canonical profile / wallet
-- ---------------------------------------------------------
create or replace function public.mathai_referrer_status_v070(p_email text)
returns table (
    found boolean,
    override_eligible boolean,
    profile_complete boolean,
    effective_use_count integer,
    has_approved_topup boolean,
    eligible boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
    v_profile_exists boolean := false;
    v_override boolean := false;
    v_profile_complete boolean := false;
    v_use_count integer := 0;
    v_topup boolean := false;
begin
    if v_email = '' then
        return query select false, false, false, 0, false, false;
        return;
    end if;

    select exists(
        select 1
        from public.student_profile_controls p
        where lower(p.email) = v_email
    )
    into v_profile_exists;

    select coalesce((
        select p.referral_eligible_override
        from public.student_profile_controls p
        where lower(p.email) = v_email
        limit 1
    ), false)
    into v_override;

    select exists(
        select 1
        from public.student_profile_controls p
        where lower(p.email) = v_email
          and trim(coalesce(p.locked_last_name, '')) <> ''
          and trim(coalesce(p.locked_first_name, '')) <> ''
          and trim(coalesce(p.school, '')) <> ''
    )
    into v_profile_complete;

    select count(*)::integer
    into v_use_count
    from (
        select 1
        from public.user_activity_events e
        where lower(e.user_email) = v_email
        limit 3
    ) q;

    select exists(
        select 1
        from public.topup_requests t
        where lower(t.user_email) = v_email
          and lower(coalesce(t.status, '')) = 'approved'
    )
    into v_topup;

    return query
    select
        (v_profile_exists or v_use_count > 0 or v_topup),
        v_override,
        v_profile_complete,
        v_use_count,
        v_topup,
        (
            v_override
            or (
                v_profile_exists
                and v_profile_complete
                and (v_topup or v_use_count >= 3)
            )
        );
end;
$$;

create or replace function public.mathai_referral_status_v070(p_email text)
returns table (
    found boolean,
    referrer_email text,
    status text,
    reward_points integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
begin
    if exists(
        select 1
        from public.referrals r
        where lower(r.referred_email) = v_email
    ) then
        return query
        select
            true,
            lower(r.referrer_email),
            r.status,
            r.reward_points
        from public.referrals r
        where lower(r.referred_email) = v_email
        order by r.created_at desc
        limit 1;
        return;
    end if;

    return query
    select false, ''::text, ''::text, 0;
end;
$$;

create or replace function public.mathai_create_referral_v070(
    p_referrer_email text,
    p_referred_email text
)
returns table (
    success boolean,
    message text,
    referral_id bigint
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_referrer text := lower(trim(coalesce(p_referrer_email, '')));
    v_referred text := lower(trim(coalesce(p_referred_email, '')));
    v_eligible boolean := false;
    v_id bigint;
begin
    if v_referrer = '' or v_referred = '' then
        return query select false, 'Email 不可為空。'::text, null::bigint;
        return;
    end if;

    if v_referrer = v_referred then
        return query select false, '不能推薦自己。'::text, null::bigint;
        return;
    end if;

    select coalesce(s.eligible, false)
    into v_eligible
    from public.mathai_referrer_status_v070(v_referrer) s
    limit 1;

    if not v_eligible then
        return query
        select false, '介紹人目前不符合推薦資格。'::text, null::bigint;
        return;
    end if;

    insert into public.referrals (
        referrer_email,
        referred_email,
        status,
        reward_points,
        reason,
        created_at,
        updated_at
    )
    values (
        v_referrer,
        v_referred,
        'pending',
        50,
        '',
        now(),
        now()
    )
    on conflict (referred_email) do update set
        referrer_email = excluded.referrer_email,
        status = 'pending',
        reward_points = 50,
        reason = '',
        awarded_at = null,
        updated_at = now()
    returning id into v_id;

    delete from public.registration_source_retries rr
    where lower(rr.user_email) = v_referred;

    return query
    select true, '推薦關係已登記成功。'::text, v_id;
end;
$$;

create or replace function public.mathai_record_use_and_award_referral_v070(
    p_email text,
    p_event_type text
)
returns table (
    event_recorded boolean,
    referral_awarded boolean,
    user_credits integer,
    referrer_email text,
    referrer_reward_applied boolean,
    message text
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
    v_event_type text := trim(coalesce(p_event_type, 'ai_use'));
    v_ref public.referrals%rowtype;
    v_referrer text := '';
    v_eligible boolean := false;
    v_month_count integer := 0;
    v_user_balance integer := 0;
    v_referrer_balance integer := 0;
begin
    if v_email = '' then
        return query
        select false, false, 0, ''::text, false, 'Email 不可為空。'::text;
        return;
    end if;

    -- 確保目前會員錢包存在，來源由 Supabase 決定。
    select b.credits
    into v_user_balance
    from public.mathai_wallet_bootstrap_v070(v_email, false) b
    limit 1;

    insert into public.user_activity_events (
        id, user_email, event_type, created_at
    )
    values (
        gen_random_uuid(), v_email, v_event_type, now()
    );

    select r.*
    into v_ref
    from public.referrals r
    where lower(r.referred_email) = v_email
      and r.status = 'pending'
    order by r.created_at desc
    limit 1;

    if not found then
        return query
        select
            true, false, coalesce(v_user_balance, 0),
            ''::text, false,
            '有效使用已記錄，沒有待發放推薦獎勵。'::text;
        return;
    end if;

    v_referrer := lower(trim(v_ref.referrer_email));

    select coalesce(s.eligible, false)
    into v_eligible
    from public.mathai_referrer_status_v070(v_referrer) s
    limit 1;

    if not v_eligible then
        update public.referrals r
        set
            status = 'rejected',
            reason = '介紹人已不符合推薦資格。',
            updated_at = now()
        where r.id = v_ref.id;

        return query
        select
            true, false, coalesce(v_user_balance, 0),
            v_referrer, false,
            '介紹人已不符合推薦資格，因此未發放點數。'::text;
        return;
    end if;

    select count(*)::integer
    into v_month_count
    from public.referrals r
    where lower(r.referrer_email) = v_referrer
      and r.status = 'awarded'
      and r.awarded_at >= date_trunc('month', now());

    if v_month_count >= 10 then
        update public.referrals r
        set
            status = 'monthly_limit',
            reason = '介紹人本月已達 10 次推薦獎勵上限。',
            updated_at = now()
        where r.id = v_ref.id;

        return query
        select
            true, false, coalesce(v_user_balance, 0),
            v_referrer, false,
            '介紹人本月已達推薦獎勵上限。'::text;
        return;
    end if;

    -- 介紹人的首次錢包也由 Supabase canonical profile 決定。
    select b.credits
    into v_referrer_balance
    from public.mathai_wallet_bootstrap_v070(v_referrer, false) b
    limit 1;

    update public.member_wallets w
    set credits = w.credits + 50, updated_at = now()
    where lower(w.email) = v_email
    returning w.credits into v_user_balance;

    update public.member_wallets w
    set credits = w.credits + 50, updated_at = now()
    where lower(w.email) = v_referrer
    returning w.credits into v_referrer_balance;

    insert into public.member_credit_ledger (
        id, user_email, delta, balance_after,
        reason, reference_type, reference_id, created_at
    )
    values
    (
        gen_random_uuid(), v_email, 50, v_user_balance,
        'referral_reward_referred', 'referral', v_ref.id::text, now()
    ),
    (
        gen_random_uuid(), v_referrer, 50, v_referrer_balance,
        'referral_reward_referrer', 'referral', v_ref.id::text, now()
    );

    update public.referrals r
    set
        status = 'awarded',
        awarded_at = now(),
        reason = '',
        updated_at = now()
    where r.id = v_ref.id;

    update public.student_profile_controls p
    set
        source_reward_status = 'awarded',
        updated_at = now()
    where lower(p.email) = v_email;

    delete from public.registration_source_retries rr
    where lower(rr.user_email) = v_email;

    return query
    select
        true, true, coalesce(v_user_balance, 0),
        v_referrer, true,
        '推薦成功，雙方各增加 50 點。'::text;
end;
$$;

-- ---------------------------------------------------------
-- G. 來源重填／來源獎勵狀態 RPC
-- ---------------------------------------------------------
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
        user_email, source_type, source_detail, status, updated_at
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
    delete from public.registration_source_retries r
    where lower(r.user_email) = lower(trim(coalesce(p_email, '')));
    return true;
end;
$$;

create or replace function public.mathai_source_claim_status(p_email text)
returns table (
    has_claim boolean,
    claim_type text,
    claim_status text
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
    v_status text := '';
begin
    if v_email = '' then
        return query select false, ''::text, ''::text;
        return;
    end if;

    select lower(coalesce(r.status, ''))
    into v_status
    from public.referrals r
    where lower(r.referred_email) = v_email
      and lower(coalesce(r.status, '')) in (
          'pending', 'processing', 'awarded', 'monthly_limit'
      )
    order by r.created_at desc
    limit 1;

    if coalesce(v_status, '') <> '' then
        return query select true, 'referral'::text, v_status;
        return;
    end if;

    if exists(
        select 1
        from public.promo_redemptions p
        where lower(p.user_email) = v_email
    ) then
        return query select true, 'promo'::text, 'awarded'::text;
        return;
    end if;

    select lower(coalesce(a.status, ''))
    into v_status
    from public.acquisition_claims a
    where lower(a.user_email) = v_email
      and lower(coalesce(a.status, '')) in (
          'pending', 'approved', 'awarded'
      )
    order by a.created_at desc
    limit 1;

    if coalesce(v_status, '') <> '' then
        return query select true, 'acquisition'::text, v_status;
        return;
    end if;

    return query select false, ''::text, ''::text;
end;
$$;

-- ---------------------------------------------------------
-- H. RPC 權限
-- ---------------------------------------------------------
revoke all on function public.mathai_profile_get_v070(text) from public;
revoke all on function public.mathai_profile_save_v070(
    text, boolean, text, text, text, text, text, text, text,
    jsonb, jsonb, text, text, text, boolean, integer, integer
) from public;
revoke all on function public.mathai_wallet_lookup_v070(text) from public;
revoke all on function public.mathai_wallet_bootstrap_v070(text, boolean) from public;
revoke all on function public.mathai_wallet_adjust_v070(
    text, integer, text, text, text
) from public;
revoke all on function public.mathai_referrer_status_v070(text) from public;
revoke all on function public.mathai_referral_status_v070(text) from public;
revoke all on function public.mathai_create_referral_v070(text, text) from public;
revoke all on function public.mathai_record_use_and_award_referral_v070(
    text, text
) from public;

grant execute on function public.mathai_profile_get_v070(text)
to anon, authenticated;
grant execute on function public.mathai_profile_save_v070(
    text, boolean, text, text, text, text, text, text, text,
    jsonb, jsonb, text, text, text, boolean, integer, integer
) to anon, authenticated;
grant execute on function public.mathai_wallet_lookup_v070(text)
to anon, authenticated;
grant execute on function public.mathai_wallet_bootstrap_v070(text, boolean)
to anon, authenticated;
grant execute on function public.mathai_wallet_adjust_v070(
    text, integer, text, text, text
) to anon, authenticated;
grant execute on function public.mathai_referrer_status_v070(text)
to anon, authenticated;
grant execute on function public.mathai_referral_status_v070(text)
to anon, authenticated;
grant execute on function public.mathai_create_referral_v070(text, text)
to anon, authenticated;
grant execute on function public.mathai_record_use_and_award_referral_v070(
    text, text
) to anon, authenticated;

revoke all on function public.mathai_save_source_retry(
    text, text, text, text
) from public;
revoke all on function public.mathai_get_source_retry(text) from public;
revoke all on function public.mathai_clear_source_retry(text) from public;
revoke all on function public.mathai_source_claim_status(text) from public;

grant execute on function public.mathai_save_source_retry(
    text, text, text, text
) to anon, authenticated;
grant execute on function public.mathai_get_source_retry(text)
to anon, authenticated;
grant execute on function public.mathai_clear_source_retry(text)
to anon, authenticated;
grant execute on function public.mathai_source_claim_status(text)
to anon, authenticated;

-- ---------------------------------------------------------
-- I. 最後檢查：只看結構，不修改點數
-- ---------------------------------------------------------
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
      'student_profile_controls',
      'member_wallets',
      'member_credit_ledger',
      'user_activity_events',
      'referrals'
  )
order by table_name;

select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
      'mathai_profile_get_v070',
      'mathai_profile_save_v070',
      'mathai_wallet_lookup_v070',
      'mathai_wallet_bootstrap_v070',
      'mathai_wallet_adjust_v070',
      'mathai_referrer_status_v070',
      'mathai_referral_status_v070',
      'mathai_create_referral_v070',
      'mathai_record_use_and_award_referral_v070'
  )
order by routine_name;
