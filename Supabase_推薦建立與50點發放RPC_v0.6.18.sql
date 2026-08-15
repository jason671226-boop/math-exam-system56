-- MathAI v0.6.18
-- 修正：
-- 1. referrals 開啟 RLS 時，Streamlit anon key 無法 direct insert。
-- 2. 舊 rejected 推薦紀錄可能造成 referred_email unique 衝突。
-- 3. 有效使用紀錄與雙方 +50 點改由 SECURITY DEFINER RPC 原子化處理。
-- 可重複執行。

-- ---------------------------------------------------------
-- A. 確保必要欄位／資料表存在
-- ---------------------------------------------------------
alter table public.student_profile_controls
    add column if not exists credits integer;

create table if not exists public.user_activity_events (
    id uuid primary key,
    user_email text not null,
    event_type text not null,
    created_at timestamptz not null default now()
);

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

create table if not exists public.credit_transactions (
    id uuid primary key,
    user_email text not null,
    points integer not null,
    reason text not null,
    reference_type text not null default '',
    reference_id text not null default '',
    created_at timestamptz not null default now()
);

create index if not exists user_activity_events_email_created_idx
    on public.user_activity_events (user_email, created_at desc);

create index if not exists referrals_referrer_status_idx
    on public.referrals (referrer_email, status, awarded_at desc);

create index if not exists credit_transactions_email_created_idx
    on public.credit_transactions (user_email, created_at desc);

-- ---------------------------------------------------------
-- B. 安全建立／重新建立推薦關係
-- ---------------------------------------------------------
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

    -- 同一被推薦人舊版若留下 rejected row，直接更新為新的 pending。
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
    select
        true,
        '推薦關係已登記成功。'::text,
        v_id;
end;
$$;

-- ---------------------------------------------------------
-- C. 記錄有效使用 + 推薦雙方各 50 點
-- ---------------------------------------------------------
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
    v_user_credits integer := 0;
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

    select *
    into v_ref
    from public.referrals
    where lower(referred_email) = v_email
      and status = 'pending'
    order by created_at desc
    limit 1;

    if not found then
        select coalesce(credits, 0)
        into v_user_credits
        from public.student_profile_controls
        where lower(email) = v_email
        limit 1;

        return query
        select
            true,
            false,
            coalesce(v_user_credits, 0),
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

        return query
        select
            true,
            false,
            coalesce((
                select credits
                from public.student_profile_controls
                where lower(email) = v_email
                limit 1
            ), 0),
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

        return query
        select
            true,
            false,
            coalesce((
                select credits
                from public.student_profile_controls
                where lower(email) = v_email
                limit 1
            ), 0),
            v_referrer,
            '介紹人本月已達推薦獎勵上限。'::text;
        return;
    end if;

    -- 兩邊各 +50；不存在的控制列也會自動建立。
    insert into public.student_profile_controls (
        email,
        credits,
        updated_at
    )
    values (
        v_email,
        50,
        now()
    )
    on conflict (email) do update set
        credits = coalesce(public.student_profile_controls.credits, 0) + 50,
        updated_at = now();

    insert into public.student_profile_controls (
        email,
        credits,
        updated_at
    )
    values (
        v_referrer,
        50,
        now()
    )
    on conflict (email) do update set
        credits = coalesce(public.student_profile_controls.credits, 0) + 50,
        updated_at = now();

    insert into public.credit_transactions (
        id,
        user_email,
        points,
        reason,
        reference_type,
        reference_id,
        created_at
    )
    values
    (
        gen_random_uuid(),
        v_email,
        50,
        'referral_reward_referred',
        'referral',
        v_ref.id::text,
        now()
    ),
    (
        gen_random_uuid(),
        v_referrer,
        50,
        'referral_reward_referrer',
        'referral',
        v_ref.id::text,
        now()
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

    select coalesce(credits, 0)
    into v_user_credits
    from public.student_profile_controls
    where lower(email) = v_email
    limit 1;

    return query
    select
        true,
        true,
        coalesce(v_user_credits, 0),
        v_referrer,
        '推薦成功，雙方各增加 50 點。'::text;
end;
$$;

revoke all on function public.mathai_create_referral(text, text) from public;
revoke all on function public.mathai_record_use_and_award_referral(text, text)
from public;

grant execute on function public.mathai_create_referral(text, text)
to anon, authenticated;
grant execute on function public.mathai_record_use_and_award_referral(text, text)
to anon, authenticated;

-- ---------------------------------------------------------
-- D. 驗證 RPC 可以執行
-- ---------------------------------------------------------
select
    routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
      'mathai_create_referral',
      'mathai_record_use_and_award_referral'
  )
order by routine_name;
