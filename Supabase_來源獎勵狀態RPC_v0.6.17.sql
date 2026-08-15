-- MathAI v0.6.17
-- 讓 Streamlit 可以安全判斷「此帳號是否已成功占用來源獎勵」。
-- 只回傳 claim 類型／狀態，不暴露學生個資。
-- 可重複執行。

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
          'pending',
          'processing',
          'awarded',
          'monthly_limit'
      )
    order by r.created_at desc nulls last
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
          'pending',
          'approved',
          'awarded'
      )
    order by a.created_at desc nulls last
    limit 1;

    if coalesce(v_status, '') <> '' then
        return query select true, 'acquisition'::text, v_status;
        return;
    end if;

    return query select false, ''::text, ''::text;
end;
$$;

revoke all on function public.mathai_source_claim_status(text) from public;
grant execute on function public.mathai_source_claim_status(text)
to anon, authenticated;

-- 目前測試帳號若尚未有成功 claim，預期 has_claim=false。
select *
from public.mathai_source_claim_status('jason6011226@gmail.com');
