-- MathAI v0.6.15
-- 解決 student_profile_controls 已啟用 RLS，
-- Streamlit 使用 anon key 時無法直接讀取推薦資格的問題。
-- 本 RPC 只回傳「是否存在／是否合格／有效使用次數」，
-- 不會把姓名、學校等會員個資暴露給前端。
-- 可重複執行。

alter table public.student_profile_controls
    add column if not exists referral_eligible_override boolean
    not null default false;

-- 管理員指定的合格推薦人
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

create or replace function public.mathai_referrer_status(p_email text)
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
    v_control_exists boolean := false;
    v_override boolean := false;
    v_profile_complete boolean := false;
    v_event_count integer := 0;
    v_item_count integer := 0;
    v_use_count integer := 0;
    v_topup boolean := false;
    v_found boolean := false;
    v_eligible boolean := false;
begin
    if v_email = '' then
        return query
        select false, false, false, 0, false, false;
        return;
    end if;

    select exists(
        select 1
        from public.user_profiles
        where lower(email) = v_email
    ) into v_profile_exists;

    select exists(
        select 1
        from public.student_profile_controls
        where lower(email) = v_email
    ) into v_control_exists;

    select coalesce((
        select referral_eligible_override
        from public.student_profile_controls
        where lower(email) = v_email
        limit 1
    ), false) into v_override;

    select exists(
        select 1
        from public.user_profiles
        where lower(email) = v_email
          and trim(coalesce(last_name, '')) <> ''
          and trim(coalesce(first_name, '')) <> ''
          and trim(coalesce(school, '')) <> ''
    ) into v_profile_complete;

    select count(*)::integer
    into v_event_count
    from (
        select 1
        from public.user_activity_events
        where lower(user_email) = v_email
        limit 3
    ) q;

    select count(*)::integer
    into v_item_count
    from (
        select 1
        from public.item_bank
        where lower(user_id) = v_email
        limit 3
    ) q;

    v_use_count := greatest(v_event_count, v_item_count);

    select exists(
        select 1
        from public.topup_requests
        where lower(user_email) = v_email
          and lower(coalesce(status, '')) = 'approved'
    ) into v_topup;

    v_found := (
        v_profile_exists
        or v_control_exists
        or v_use_count > 0
        or v_topup
    );

    v_eligible := (
        v_override
        or (
            v_found
            and v_profile_complete
            and (v_topup or v_use_count >= 3)
        )
    );

    return query
    select
        v_found,
        v_override,
        v_profile_complete,
        v_use_count,
        v_topup,
        v_eligible;
end;
$$;

revoke all on function public.mathai_referrer_status(text) from public;
grant execute on function public.mathai_referrer_status(text) to anon, authenticated;

-- 驗證指定帳號；預期 override_eligible=true、eligible=true
select *
from public.mathai_referrer_status('jason671226@gmail.com');

-- 可順便檢查另一個帳號目前累積幾次有效使用
select *
from public.mathai_referrer_status('jason621226@gmail.com');
