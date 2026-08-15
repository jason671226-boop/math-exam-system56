-- =========================================================
-- MathAI v0.8.5 Private Beta｜新會員初始點數 200 點
-- 安全原則：
-- 1. 不修改任何已存在 member_wallets 的餘額。
-- 2. 只改「未來新建立」wallet 的預設值與 canonical bootstrap 新會員分支。
-- 3. 舊會員／legacy fallback 仍保留原有 100 點邏輯，避免誤加點數。
-- =========================================================

begin;

alter table public.member_wallets
    alter column credits set default 200;

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
            v_initial := 200;
            v_source := 'new_account_200';
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

commit;

-- 驗證（只讀）：
-- select column_default
-- from information_schema.columns
-- where table_schema='public' and table_name='member_wallets' and column_name='credits';
--
-- 不要用正式會員測試建立新 wallet；建議 Private Beta 測試帳號驗證後，
-- 應看到 migration_source = 'new_account_200' 且 credits = 200。
