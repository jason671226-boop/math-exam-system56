-- STAGING ONLY. DO NOT APPLY TO PRODUCTION.
-- MathAI testing auth ACL repair (additive, idempotent).
--
-- Staging already applied 014_testing_auth_bridge.sql before the service_role
-- EXECUTE revokes were added.  This repair removes the default service_role
-- EXECUTE privilege from every testing-auth function so the final ACL matches
-- the minimal contract:
--   prepare(text,text,timestamptz) -> anon
--   reveal(text,text)            -> anon
--   fail(text,text)              -> anon
--   consume(text,text)           -> authenticated
--   email_hook(jsonb)            -> supabase_auth_admin
--
-- postgres owner privileges are intentionally preserved.  No RLS change, no
-- table grants, no data change.

revoke execute on function public.mathai_testing_auth_prepare(text,text,timestamptz) from service_role;
revoke execute on function public.mathai_testing_auth_reveal(text,text) from service_role;
revoke execute on function public.mathai_testing_auth_fail(text,text) from service_role;
revoke execute on function public.mathai_testing_auth_consume(text,text) from service_role;
revoke execute on function public.mathai_testing_auth_email_hook(jsonb) from service_role;
