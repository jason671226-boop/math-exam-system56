-- MathAI Staging 004: read-only verification plus transactional A/B smoke test.
-- The smoke test resolves the existing Staging Auth users by email.

-- A. Schema/table existence
select table_schema, table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'learning_students', 'student_access', 'diagnostic_attempts',
    'diagnostic_item_results', 'knowledge_mastery', 'thinking_skill_evidence'
  )
order by table_name;

-- B. Primary keys, unique constraints and foreign keys
select constraint_schema, table_name, constraint_name, constraint_type
from information_schema.table_constraints
where constraint_schema = 'public'
  and table_name in (
    'learning_students', 'student_access', 'diagnostic_attempts',
    'diagnostic_item_results', 'knowledge_mastery', 'thinking_skill_evidence'
  )
order by table_name, constraint_type, constraint_name;

-- C. Indexes
select schemaname, tablename, indexname, indexdef
from pg_catalog.pg_indexes
where schemaname = 'public'
  and tablename in (
    'learning_students', 'student_access', 'diagnostic_attempts',
    'diagnostic_item_results', 'knowledge_mastery', 'thinking_skill_evidence'
  )
order by tablename, indexname;

-- D. RLS enabled
select namespace.nspname as schema_name, class.relname as table_name,
       class.relrowsecurity as rls_enabled, class.relforcerowsecurity as force_rls
from pg_catalog.pg_class as class
join pg_catalog.pg_namespace as namespace on namespace.oid = class.relnamespace
where namespace.nspname = 'public'
  and class.relname in (
    'learning_students', 'student_access', 'diagnostic_attempts',
    'diagnostic_item_results', 'knowledge_mastery', 'thinking_skill_evidence'
  )
order by class.relname;

-- E. Policies: expect SELECT/INSERT/UPDATE only; no DELETE policy.
select schemaname, tablename, policyname, roles, cmd, qual, with_check
from pg_catalog.pg_policies
where schemaname = 'public'
  and tablename in (
    'student_access', 'diagnostic_attempts', 'diagnostic_item_results',
    'knowledge_mastery', 'thinking_skill_evidence'
  )
order by tablename, policyname;

-- F. Function security and privileges
select routine_schema, routine_name, security_type
from information_schema.routines
where (routine_schema, routine_name) in (
  ('private', 'can_access_student'), ('private', 'set_updated_at')
);

select grantee, privilege_type
from information_schema.routine_privileges
where specific_schema = 'private'
  and routine_name in ('can_access_student', 'set_updated_at')
order by routine_name, grantee, privilege_type;

-- G. Unauthenticated grant audit: expect zero rows.
select grantee, table_schema, table_name, privilege_type
from information_schema.role_table_grants
where grantee = 'anon'
  and table_schema = 'public'
  and table_name in (
    'learning_students', 'student_access', 'diagnostic_attempts', 'diagnostic_item_results',
    'knowledge_mastery', 'thinking_skill_evidence'
  );

-- Authenticated grants: expect SELECT/INSERT/UPDATE only on learning-data tables,
-- SELECT only on student_access, and no DELETE anywhere.
select grantee, table_schema, table_name, privilege_type
from information_schema.role_table_grants
where grantee = 'authenticated'
  and table_schema = 'public'
  and table_name in (
    'learning_students', 'student_access', 'diagnostic_attempts',
    'diagnostic_item_results', 'knowledge_mastery', 'thinking_skill_evidence'
  )
order by table_name, privilege_type;

-- Fail fast if client table privileges differ from the deny-by-default design.
-- learning_students is provisioned outside the student client flow;
-- student_access is readable but cannot be self-granted by authenticated users.
do $$
declare
  table_name text;
  privilege_name text;
begin
  foreach table_name in array array[
    'learning_students', 'student_access', 'diagnostic_attempts',
    'diagnostic_item_results', 'knowledge_mastery', 'thinking_skill_evidence'
  ] loop
    foreach privilege_name in array array['SELECT', 'INSERT', 'UPDATE', 'DELETE'] loop
      if pg_catalog.has_table_privilege(
        'anon', pg_catalog.format('public.%I', table_name), privilege_name
      ) then
        raise exception 'FAIL: anon unexpectedly has % on public.%',
          privilege_name, table_name;
      end if;
    end loop;
  end loop;

  if not pg_catalog.has_table_privilege(
    'authenticated', 'public.student_access', 'SELECT'
  ) then
    raise exception 'FAIL: authenticated lacks SELECT on public.student_access';
  end if;
  foreach privilege_name in array array['INSERT', 'UPDATE', 'DELETE'] loop
    if pg_catalog.has_table_privilege(
      'authenticated', 'public.student_access', privilege_name
    ) then
      raise exception 'FAIL: authenticated unexpectedly has % on public.student_access',
        privilege_name;
    end if;
  end loop;

  foreach privilege_name in array array['SELECT', 'INSERT', 'UPDATE', 'DELETE'] loop
    if pg_catalog.has_table_privilege(
      'authenticated', 'public.learning_students', privilege_name
    ) then
      raise exception 'FAIL: authenticated unexpectedly has % on public.learning_students',
        privilege_name;
    end if;
  end loop;

  foreach table_name in array array[
    'diagnostic_attempts', 'diagnostic_item_results',
    'knowledge_mastery', 'thinking_skill_evidence'
  ] loop
    foreach privilege_name in array array['SELECT', 'INSERT', 'UPDATE'] loop
      if not pg_catalog.has_table_privilege(
        'authenticated', pg_catalog.format('public.%I', table_name), privilege_name
      ) then
        raise exception 'FAIL: authenticated lacks % on public.%',
          privilege_name, table_name;
      end if;
    end loop;
    if pg_catalog.has_table_privilege(
      'authenticated', pg_catalog.format('public.%I', table_name), 'DELETE'
    ) then
      raise exception 'FAIL: authenticated unexpectedly has DELETE on public.%', table_name;
    end if;
  end loop;
end $$;

-- H. Student A/B RLS smoke test.
-- Prerequisite: these Auth users must already exist in Staging Auth:
-- student-a-staging@example.com and student-b-staging@example.com.
begin;

-- Resolve real Auth identities without creating or modifying auth.users.
-- Transaction-local settings keep the UUIDs available after SET ROLE and
-- disappear when the final ROLLBACK ends the smoke test.
do $$
declare
  student_a_user_id uuid;
  student_b_user_id uuid;
begin
  select auth_user.id into student_a_user_id
  from auth.users as auth_user
  where pg_catalog.lower(auth_user.email) = 'student-a-staging@example.com';

  select auth_user.id into student_b_user_id
  from auth.users as auth_user
  where pg_catalog.lower(auth_user.email) = 'student-b-staging@example.com';

  if student_a_user_id is null then
    raise exception 'Missing Staging Auth user: student-a-staging@example.com';
  end if;
  if student_b_user_id is null then
    raise exception 'Missing Staging Auth user: student-b-staging@example.com';
  end if;

  perform pg_catalog.set_config(
    'mathai.smoke.student_a_user_id', student_a_user_id::text, true
  );
  perform pg_catalog.set_config(
    'mathai.smoke.student_b_user_id', student_b_user_id::text, true
  );
end $$;

insert into public.learning_students (id, display_name) values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Synthetic Student A'),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Synthetic Student B');
insert into public.student_access (user_id, student_id, role) values
  (pg_catalog.current_setting('mathai.smoke.student_a_user_id')::uuid,
   'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'owner'),
  (pg_catalog.current_setting('mathai.smoke.student_b_user_id')::uuid,
   'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'owner');

set local role authenticated;
select pg_catalog.set_config(
  'request.jwt.claim.sub',
  pg_catalog.current_setting('mathai.smoke.student_a_user_id'),
  true
);

-- Student A can insert/read/update own rows.
insert into public.knowledge_mastery (
  student_id, profile_id, knowledge_id, mastery_status, mastery_score,
  confidence, evidence_count, weighted_credit
) values (
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'G5_PREREQUISITE_BASELINE',
  'G5-K001', 'learning', 60, 0.5, 2, 1
);
update public.knowledge_mastery set mastery_score = 65
where student_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
  and profile_id = 'G5_PREREQUISITE_BASELINE' and knowledge_id = 'G5-K001';

insert into public.diagnostic_attempts (
  id, student_id, attempt_key, profile_id, source_type, completed_at
) values (
  'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  'G5_PREREQUISITE_BASELINE', 'diagnostic', pg_catalog.now()
);
insert into public.diagnostic_item_results (
  attempt_id, question_id, credit, source_type, answer_payload
) values (
  'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'STAGING-SMOKE-001', 1,
  'diagnostic', '{"answer":"synthetic"}'::jsonb
);
insert into public.thinking_skill_evidence (
  student_id, profile_id, thinking_skill_id, score, confidence, evidence_count
) values (
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'G5_PREREQUISITE_BASELINE',
  'TS-LOGIC', 60, 0.5, 2
);
select * from public.knowledge_mastery
where student_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
select * from public.diagnostic_attempts
where student_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
select result.* from public.diagnostic_item_results as result
join public.diagnostic_attempts as attempt on attempt.id = result.attempt_id
where attempt.student_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
select * from public.thinking_skill_evidence
where student_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
select * from public.knowledge_mastery
where student_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'; -- expect zero rows

-- Cross-student INSERT must fail; the block catches only the expected RLS error.
do $$
begin
  begin
    insert into public.knowledge_mastery (
      student_id, profile_id, knowledge_id, mastery_status, mastery_score,
      confidence, evidence_count, weighted_credit
    ) values (
      'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'G5_PREREQUISITE_BASELINE',
      'G5-K001', 'learning', 60, 0.5, 2, 1
    );
    raise exception 'FAIL: cross-student insert unexpectedly succeeded';
  exception when insufficient_privilege then
    raise notice 'PASS: cross-student insert denied';
  end;
end $$;

-- Cross-student UPDATE must affect zero rows for Student A.
do $$
declare affected integer;
begin
  update public.knowledge_mastery set mastery_score = 99
  where student_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
  get diagnostics affected = row_count;
  if affected <> 0 then
    raise exception 'FAIL: cross-student update affected % rows', affected;
  end if;
  raise notice 'PASS: cross-student update hidden by RLS';
end $$;

-- Student B can write/read own data and cannot see Student A.
reset role;
set local role authenticated;
select pg_catalog.set_config(
  'request.jwt.claim.sub',
  pg_catalog.current_setting('mathai.smoke.student_b_user_id'),
  true
);
insert into public.knowledge_mastery (
  student_id, profile_id, knowledge_id, mastery_status, mastery_score,
  confidence, evidence_count, weighted_credit
) values (
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'G5_COMPETITION_CORE',
  'G5-K001', 'basic', 75, 0.5, 2, 1.5
);
select * from public.knowledge_mastery
where student_id = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'; -- expect one row
select * from public.knowledge_mastery
where student_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'; -- expect zero rows

rollback; -- Always removes synthetic learning rows/mappings/test mastery.
