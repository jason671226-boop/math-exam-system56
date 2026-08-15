-- MathAI v0.6.19
-- 核心修正：
-- 1. 點數不再依賴 user_profiles / student_profile_controls 的欄位與 RLS。
-- 2. 建立專用 member_wallets，Email 為唯一錢包主鍵。
-- 3. 所有加扣點改由 SECURITY DEFINER RPC 完成。
-- 4. 推薦建立後必須能被 mathai_referral_status 查到才算真正成功。
-- 5. 有效使用與推薦雙方 +50 點在同一資料庫交易中完成。
-- 可重複執行。

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

alter table public.member_wallets enable row level security;
alter table public.member_credit_ledger enable row level security;

-- 取得／建立錢包。
-- 第一次建立時使用 App 當下已知的舊點數，完成舊系統 → 雲端錢包遷移。
create or replace function public.mathai_wallet_get_or_create(
    p_email text,
    p_initial_credits integer default 100
)
returns table (
    credits integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
    v_initial integer := greatest(coalesce(p_initial_credits, 100), 0);
    v_credits integer;
begin
    if v_email = '' then
        return query select 0;
        return;
    end if;

    insert into public.member_wallets (
        email,
        credits,
        created_at,
        updated_at
    )
    values (
        v_email,
        v_initial,
        now(),
        now()
    )
    on conflict (email) do nothing;

    select w.credits
    into v_credits
    from public.member_wallets w
    where lower(w.email) = v_email
    limit 1;

    return query select coalesce(v_credits, v_initial);
end;
$$;

-- 統一的點數加扣 RPC
create or replace function public.mathai_wallet_adjust(
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
    v_balance integer;
begin
    if v_email = '' or v_delta = 0 then
        return query
        select false, 0, 'Email 或點數異動值不正確。'::text;
        return;
    end if;

    insert into public.member_wallets (
        email,
        credits,
        created_at,
        updated_at
    )
    values (
        v_email,
        100,
        now(),
        now()
    )
    on conflict (email) do nothing;

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

    update public.member_wallets
    set
        credits = credits + v_delta,
        updated_at = now()
    where lower(email) = v_email
    returning credits into v_balance;

    insert into public.member_credit_ledger (
        id,
        user_email,
        delta,
        balance_after,
        reason,
        reference_type,
        reference_id,
        created_at
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

-- 查推薦關係，不暴露其他會員資料
create or replace function public.mathai_referral_status(p_email text)
returns table (
    found boolean,
    referrer_email text,
    status text,
    reward_points integer
)
language sql
security definer
set search_path = public
as $$
    select
        true,
        lower(r.referrer_email),
        r.status,
        r.reward_points
    from public.referrals r
    where lower(r.referred_email) = lower(trim(coalesce(p_email, '')))
    order by r.created_at desc
    limit 1;
$$;

-- 建立推薦關係
create or replace function public.mathai_create_referral(
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
        return query
        select false, 'Email 不可為空。'::text, null::bigint;
        return;
    end if;

    if v_referrer = v_referred then
        return query
        select false, '不能推薦自己。'::text, null::bigint;
        return;
    end if;

    select coalesce(s.eligible, false)
    into v_eligible
    from public.mathai_referrer_status(v_referrer) s
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

    delete from public.registration_source_retries
    where lower(user_email) = v_referred;

    return query
    select true, '推薦關係已登記成功。'::text, v_id;
end;
$$;

-- 記錄有效使用 + 發推薦獎勵
create or replace function public.mathai_record_use_and_award_referral(
    p_email text,
    p_event_type text
)
returns table (
    event_recorded boolean,
    referral_awarded boolean,
    user_credits integer,
    referrer_email text,
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
        select false, false, 0, ''::text, 'Email 不可為空。'::text;
        return;
    end if;

    insert into public.user_activity_events (
        id,
        user_email,
        event_type,
        created_at
    )
    values (
        gen_random_uuid(),
        v_email,
        v_event_type,
        now()
    );

    -- 確保被推薦人錢包存在；正常情況登入時已建立。
    insert into public.member_wallets (
        email,
        credits,
        created_at,
        updated_at
    )
    values (
        v_email,
        100,
        now(),
        now()
    )
    on conflict (email) do nothing;

    select *
    into v_ref
    from public.referrals
    where lower(referred_email) = v_email
      and status = 'pending'
    order by created_at desc
    limit 1;

    if not found then
        select credits
        into v_user_balance
        from public.member_wallets
        where lower(email) = v_email
        limit 1;

        return query
        select
            true,
            false,
            coalesce(v_user_balance, 0),
            ''::text,
            '有效使用已記錄，沒有待發放推薦獎勵。'::text;
        return;
    end if;

    v_referrer := lower(trim(v_ref.referrer_email));

    select coalesce(s.eligible, false)
    into v_eligible
    from public.mathai_referrer_status(v_referrer) s
    limit 1;

    if not v_eligible then
        update public.referrals
        set
            status = 'rejected',
            reason = '介紹人已不符合推薦資格。',
            updated_at = now()
        where id = v_ref.id;

        select credits
        into v_user_balance
        from public.member_wallets
        where lower(email) = v_email
        limit 1;

        return query
        select
            true,
            false,
            coalesce(v_user_balance, 0),
            v_referrer,
            '介紹人已不符合推薦資格，因此未發放點數。'::text;
        return;
    end if;

    select count(*)::integer
    into v_month_count
    from public.referrals
    where lower(referrer_email) = v_referrer
      and status = 'awarded'
      and awarded_at >= date_trunc('month', now());

    if v_month_count >= 10 then
        update public.referrals
        set
            status = 'monthly_limit',
            reason = '介紹人本月已達 10 次推薦獎勵上限。',
            updated_at = now()
        where id = v_ref.id;

        select credits
        into v_user_balance
        from public.member_wallets
        where lower(email) = v_email
        limit 1;

        return query
        select
            true,
            false,
            coalesce(v_user_balance, 0),
            v_referrer,
            '介紹人本月已達推薦獎勵上限。'::text;
        return;
    end if;

    -- 介紹人若尚未登入 v0.6.19，先建立 100 點錢包；
    -- 之後登入時不會覆蓋已有的雲端餘額。
    insert into public.member_wallets (
        email,
        credits,
        created_at,
        updated_at
    )
    values (
        v_referrer,
        100,
        now(),
        now()
    )
    on conflict (email) do nothing;

    update public.member_wallets
    set credits = credits + 50, updated_at = now()
    where lower(email) = v_email
    returning credits into v_user_balance;

    update public.member_wallets
    set credits = credits + 50, updated_at = now()
    where lower(email) = v_referrer
    returning credits into v_referrer_balance;

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

    update public.referrals
    set
        status = 'awarded',
        awarded_at = now(),
        reason = '',
        updated_at = now()
    where id = v_ref.id;

    delete from public.registration_source_retries
    where lower(user_email) = v_email;

    return query
    select
        true,
        true,
        coalesce(v_user_balance, 0),
        v_referrer,
        '推薦成功，雙方各增加 50 點。'::text;
end;
$$;

revoke all on function public.mathai_wallet_get_or_create(text, integer) from public;
revoke all on function public.mathai_wallet_adjust(text, integer, text, text, text) from public;
revoke all on function public.mathai_referral_status(text) from public;
revoke all on function public.mathai_create_referral(text, text) from public;
revoke all on function public.mathai_record_use_and_award_referral(text, text) from public;

grant execute on function public.mathai_wallet_get_or_create(text, integer)
to anon, authenticated;
grant execute on function public.mathai_wallet_adjust(text, integer, text, text, text)
to anon, authenticated;
grant execute on function public.mathai_referral_status(text)
to anon, authenticated;
grant execute on function public.mathai_create_referral(text, text)
to anon, authenticated;
grant execute on function public.mathai_record_use_and_award_referral(text, text)
to anon, authenticated;

-- 驗證必要函式已存在
select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
      'mathai_wallet_get_or_create',
      'mathai_wallet_adjust',
      'mathai_referral_status',
      'mathai_create_referral',
      'mathai_record_use_and_award_referral'
  )
order by routine_name;
