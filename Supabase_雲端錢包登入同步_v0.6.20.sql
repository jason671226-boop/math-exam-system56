-- MathAI v0.6.20｜雲端錢包登入同步
-- 可重複執行。
--
-- 目標：
-- 1. 查不到錢包時，不再自動用 100 點建立。
-- 2. 只有「登入同步」RPC 可以做第一次錢包遷移。
-- 3. 介紹人尚未建立錢包時，推薦 +50 先進 pending_wallet_credits，
--    下次登入再自動加進正確的舊餘額。
-- 4. 避免既有會員 85 點被誤當成 100 點。

create table if not exists public.pending_wallet_credits (
    email text primary key,
    pending_points integer not null default 0,
    reason text not null default '',
    updated_at timestamptz not null default now()
);

alter table public.pending_wallet_credits enable row level security;

-- 只查錢包，不建立
create or replace function public.mathai_wallet_lookup(p_email text)
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

-- 登入時唯一的「建立／同步錢包」入口
create or replace function public.mathai_wallet_migrate_or_sync(
    p_email text,
    p_legacy_credits integer default null
)
returns table (
    success boolean,
    credits integer,
    pending_applied integer,
    message text
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text := lower(trim(coalesce(p_email, '')));
    v_balance integer;
    v_pending integer := 0;
    v_exists boolean := false;
begin
    if v_email = '' then
        return query
        select false, 0, 0, 'Email 不可為空。'::text;
        return;
    end if;

    select exists(
        select 1
        from public.member_wallets w
        where lower(w.email) = v_email
    )
    into v_exists;

    if not v_exists then
        if p_legacy_credits is null then
            return query
            select
                false,
                0,
                0,
                '此舊會員尚無雲端錢包，且找不到可安全遷移的舊點數。'::text;
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
            greatest(p_legacy_credits, 0),
            now(),
            now()
        )
        on conflict (email) do nothing;
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
        select
            gen_random_uuid(),
            v_email,
            v_pending,
            w.credits,
            'pending_wallet_credit_applied',
            'wallet_migration',
            '',
            now()
        from public.member_wallets w
        where lower(w.email) = v_email;

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
        true,
        coalesce(v_balance, 0),
        v_pending,
        case
            when v_pending > 0
                then '雲端錢包同步完成，待領取點數已補入。'
            else '雲端錢包同步完成。'
        end::text;
end;
$$;

-- 重新建立推薦獎勵 RPC：
-- 被推薦人一定要已有錢包；
-- 介紹人沒有錢包時，不用 100 點猜測，先保留 50 點。
drop function if exists public.mathai_record_use_and_award_referral(text, text);

create function public.mathai_record_use_and_award_referral(
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
    v_referrer_has_wallet boolean := false;
begin
    if v_email = '' then
        return query
        select false, false, 0, ''::text, false, 'Email 不可為空。'::text;
        return;
    end if;

    if not exists(
        select 1
        from public.member_wallets w
        where lower(w.email) = v_email
    ) then
        return query
        select
            false,
            false,
            0,
            ''::text,
            false,
            '目前登入帳號尚未完成雲端錢包同步，因此不執行點數異動。'::text;
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

    select r.*
    into v_ref
    from public.referrals r
    where lower(r.referred_email) = v_email
      and r.status = 'pending'
    order by r.created_at desc
    limit 1;

    if not found then
        select w.credits
        into v_user_balance
        from public.member_wallets w
        where lower(w.email) = v_email
        limit 1;

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
    from public.mathai_referrer_status(v_referrer) s
    limit 1;

    if not v_eligible then
        update public.referrals r
        set
            status = 'rejected',
            reason = '介紹人已不符合推薦資格。',
            updated_at = now()
        where r.id = v_ref.id;

        select w.credits
        into v_user_balance
        from public.member_wallets w
        where lower(w.email) = v_email
        limit 1;

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

        select w.credits
        into v_user_balance
        from public.member_wallets w
        where lower(w.email) = v_email
        limit 1;

        return query
        select
            true, false, coalesce(v_user_balance, 0),
            v_referrer, false,
            '介紹人本月已達推薦獎勵上限。'::text;
        return;
    end if;

    -- 被推薦人一定已有 wallet，直接 +50
    update public.member_wallets w
    set
        credits = w.credits + 50,
        updated_at = now()
    where lower(w.email) = v_email
    returning w.credits into v_user_balance;

    insert into public.member_credit_ledger (
        id, user_email, delta, balance_after,
        reason, reference_type, reference_id, created_at
    )
    values (
        gen_random_uuid(),
        v_email,
        50,
        v_user_balance,
        'referral_reward_referred',
        'referral',
        v_ref.id::text,
        now()
    );

    select exists(
        select 1
        from public.member_wallets w
        where lower(w.email) = v_referrer
    )
    into v_referrer_has_wallet;

    if v_referrer_has_wallet then
        update public.member_wallets w
        set
            credits = w.credits + 50,
            updated_at = now()
        where lower(w.email) = v_referrer
        returning w.credits into v_referrer_balance;

        insert into public.member_credit_ledger (
            id, user_email, delta, balance_after,
            reason, reference_type, reference_id, created_at
        )
        values (
            gen_random_uuid(),
            v_referrer,
            50,
            v_referrer_balance,
            'referral_reward_referrer',
            'referral',
            v_ref.id::text,
            now()
        );
    else
        insert into public.pending_wallet_credits (
            email,
            pending_points,
            reason,
            updated_at
        )
        values (
            v_referrer,
            50,
            'referral_reward_referrer',
            now()
        )
        on conflict (email) do update set
            pending_points =
                public.pending_wallet_credits.pending_points + 50,
            reason = 'referral_reward_referrer',
            updated_at = now();
    end if;

    update public.referrals r
    set
        status = 'awarded',
        awarded_at = now(),
        reason = '',
        updated_at = now()
    where r.id = v_ref.id;

    delete from public.registration_source_retries rr
    where lower(rr.user_email) = v_email;

    return query
    select
        true,
        true,
        coalesce(v_user_balance, 0),
        v_referrer,
        v_referrer_has_wallet,
        case
            when v_referrer_has_wallet
                then '推薦成功，雙方各增加 50 點。'
            else
                '推薦成功；被推薦人已加 50 點，介紹人的 50 點將在下次登入時自動補入。'
        end::text;
end;
$$;

revoke all on function public.mathai_wallet_lookup(text) from public;
revoke all on function public.mathai_wallet_migrate_or_sync(text, integer) from public;
revoke all on function public.mathai_record_use_and_award_referral(text, text)
from public;

grant execute on function public.mathai_wallet_lookup(text)
to anon, authenticated;
grant execute on function public.mathai_wallet_migrate_or_sync(text, integer)
to anon, authenticated;
grant execute on function public.mathai_record_use_and_award_referral(text, text)
to anon, authenticated;

select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
      'mathai_wallet_lookup',
      'mathai_wallet_migrate_or_sync',
      'mathai_record_use_and_award_referral'
  )
order by routine_name;
