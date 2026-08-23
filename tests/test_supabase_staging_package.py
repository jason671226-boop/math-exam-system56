from pathlib import Path
import unittest


class SupabaseStagingPackageTests(unittest.TestCase):
    ROOT = Path("migrations/staging")

    def test_emergency_rollback_refuses_non_smoke_or_non_synthetic_data(self):
        rollback = (self.ROOT / "rollback_staging.sql").read_text(encoding="utf-8")
        self.assertIn("STAGING ONLY. DO NOT APPLY TO PRODUCTION", rollback)
        self.assertIn("REFUSED: non-synthetic students exist", rollback)
        self.assertIn("REFUSED: non-smoke learning data exists", rollback)
        self.assertIn("profile_id <> 'STAGING_SMOKE'", rollback)
        self.assertIn("student-a-staging@example.com", rollback)
        self.assertIn("student-b-staging@example.com", rollback)
    FILES = (
        "001_student_ownership.sql",
        "002_mastery_persistence.sql",
        "003_mastery_rls.sql",
        "004_verify_staging.sql",
        "005_smoke_test_cleanup_policy.sql",
        "006_bootstrap_smoke_students.sql",
        "007_repair_smoke_cleanup_rls.sql",
        "008_teacher_feedback.sql",
        "009_repair_teacher_feedback_access.sql",
        "010_index_teacher_access_student.sql",
        "011_security_hardening.sql",
        "012_beta_feedback.sql",
        "013_verified_email_registration.sql",
        "014_testing_auth_bridge.sql",
        "015_testing_auth_acl_repair.sql",
        "rollback_staging.sql",
    )

    @classmethod
    def setUpClass(cls):
        cls.sql = {
            name: (cls.ROOT / name).read_text(encoding="utf-8")
            for name in cls.FILES
        }

    def test_exact_staging_package_exists(self):
        self.assertEqual(
            {path.name for path in self.ROOT.glob("*.sql")}, set(self.FILES)
        )

    def test_execution_files_use_qualified_application_objects(self):
        combined = "\n".join(self.sql[name] for name in self.FILES[:3])
        for table in (
            "learning_students", "student_access", "diagnostic_attempts",
            "diagnostic_item_results", "knowledge_mastery", "thinking_skill_evidence",
        ):
            self.assertIn(f"public.{table}", combined)
        for function in ("private.set_updated_at", "private.can_access_student"):
            self.assertIn(function, combined)
        for index, table in (
            ("student_access_student_idx", "public.student_access"),
            ("diagnostic_attempts_student_profile_completed_idx", "public.diagnostic_attempts"),
            ("knowledge_mastery_student_status_idx", "public.knowledge_mastery"),
            ("thinking_skill_evidence_student_profile_idx", "public.thinking_skill_evidence"),
        ):
            self.assertIn(f"create index {index}", combined)
            self.assertIn(f"on {table}", combined)

    def test_updated_at_triggers_are_only_on_required_tables(self):
        combined = self.sql["001_student_ownership.sql"] + self.sql["002_mastery_persistence.sql"]
        for table in ("learning_students", "knowledge_mastery", "thinking_skill_evidence"):
            self.assertIn(f"before update on public.{table}", combined)
        self.assertNotIn("before update on public.diagnostic_attempts", combined)
        self.assertNotIn("before update on public.diagnostic_item_results", combined)

    def test_rls_is_owner_mapped_without_delete_or_self_grant(self):
        rls = self.sql["003_mastery_rls.sql"]
        self.assertIn("set search_path = ''", rls)
        self.assertIn("grant execute on function private.can_access_student(uuid) to authenticated", rls)
        self.assertNotIn("grant insert on public.student_access", rls)
        self.assertNotIn("for delete", rls.lower())
        for table in (
            "diagnostic_attempts", "diagnostic_item_results",
            "knowledge_mastery", "thinking_skill_evidence",
        ):
            for operation in ("select", "insert", "update"):
                self.assertIn(f"create policy {table}_{operation}_owned", rls)

    def test_verification_covers_schema_security_and_ab_isolation(self):
        verify = self.sql["004_verify_staging.sql"]
        for token in (
            "information_schema.tables", "information_schema.table_constraints",
            "pg_catalog.pg_indexes", "pg_catalog.pg_policies", "relrowsecurity",
            "information_schema.routine_privileges", "grantee = 'anon'",
            "Synthetic Student A", "Synthetic Student B", "cross-student insert denied",
            "pg_catalog.has_table_privilege", "rollback;",
        ):
            self.assertIn(token, verify)

        self.assertNotIn("set local role anon", verify)
        self.assertNotIn("select * from public.knowledge_mastery; -- expect zero rows", verify)

    def test_verification_asserts_expected_client_table_privileges(self):
        verify = self.sql["004_verify_staging.sql"]
        for token in (
            "'anon', pg_catalog.format('public.%I', table_name), privilege_name",
            "authenticated lacks SELECT on public.student_access",
            "authenticated unexpectedly has % on public.learning_students",
            "authenticated lacks % on public.%",
            "authenticated unexpectedly has DELETE on public.%",
        ):
            self.assertIn(token, verify)

    def test_verification_resolves_existing_auth_users_without_auth_writes(self):
        verify = self.sql["004_verify_staging.sql"]
        for token in (
            "from auth.users as auth_user",
            "student-a-staging@example.com",
            "student-b-staging@example.com",
            "Missing Staging Auth user: student-a-staging@example.com",
            "Missing Staging Auth user: student-b-staging@example.com",
            "mathai.smoke.student_a_user_id",
            "mathai.smoke.student_b_user_id",
        ):
            self.assertIn(token, verify)

        self.assertNotIn("11111111-1111-4111-8111-111111111111", verify)
        self.assertNotIn("22222222-2222-4222-8222-222222222222", verify)
        normalized = " ".join(verify.lower().split())
        for forbidden in (
            "insert into auth.users",
            "update auth.users",
            "delete from auth.users",
        ):
            self.assertNotIn(forbidden, normalized)

    def test_rollback_is_scoped_and_excludes_existing_business_tables(self):
        rollback = self.sql["rollback_staging.sql"]
        for forbidden in ("wallet", "points", "referral", "auth.users"):
            self.assertNotIn(f"drop table {forbidden}", rollback.lower())
        self.assertNotIn("drop schema", rollback.lower())
        self.assertNotIn("drop extension", rollback.lower())

    def test_cleanup_repair_is_staging_only_and_minimal(self):
        repair = self.sql["007_repair_smoke_cleanup_rls.sql"]
        self.assertIn("STAGING ONLY. DO NOT APPLY TO PRODUCTION", repair)
        self.assertEqual(repair.count("profile_id = 'STAGING_SMOKE'"), 3)
        self.assertEqual(repair.count("private.can_access_student(student_id)"), 3)
        for table in (
            "diagnostic_attempts", "knowledge_mastery", "thinking_skill_evidence"
        ):
            self.assertIn(f"grant delete on public.{table} to authenticated", repair)
            self.assertIn(f"drop policy if exists {table}_delete_staging_smoke_owned", repair)
        for forbidden in (
            "service_role", "security definer", "disable row level security",
            "delete from public.student_access", "delete from public.learning_students",
        ):
            self.assertNotIn(forbidden, repair.lower())

    def test_teacher_feedback_migration_is_secure_and_independent(self):
        sql = self.sql["008_teacher_feedback.sql"]
        for token in (
            "create table if not exists public.teacher_feedback",
            "student_id uuid not null references public.learning_students",
            "recorded_by uuid not null references auth.users",
            "teacher_feedback_scope_mapping_check",
            "scope_type in ('overall', 'knowledge', 'thinking_skill')",
            "recorded_by = (select auth.uid())",
            "from public.teacher_access as access",
            "private.can_access_student(student_id)",
            "grant select, insert, delete on public.teacher_feedback to authenticated",
            "profile_id = 'STAGING_SMOKE'",
        ):
            self.assertIn(token, sql)
        normalized = " ".join(sql.lower().split())
        for forbidden in (
            "service_role", "disable row level security", "for update to authenticated",
            "grant update",
            "insert into public.knowledge_mastery", "update public.knowledge_mastery",
            "insert into public.thinking_skill_evidence", "update public.thinking_skill_evidence",
        ):
            self.assertNotIn(forbidden, normalized)

    def test_teacher_access_repair_is_staging_scoped_and_idempotent(self):
        sql = self.sql["009_repair_teacher_feedback_access.sql"]
        for token in (
            "STAGING ONLY. DO NOT APPLY TO PRODUCTION",
            "create table if not exists public.teacher_access",
            "teacher_id = (select auth.uid())",
            "profile_id = 'STAGING_SMOKE'",
            "student-a-staging@example.com",
            "student-b-staging@example.com",
            "on conflict (teacher_id, student_id) do nothing",
        ):
            self.assertIn(token, sql)
        normalized = " ".join(sql.lower().split())
        for forbidden in ("service_role", "disable row level security", "security definer"):
            self.assertNotIn(forbidden, normalized)

    def test_testing_auth_bridge_proposal_is_credential_safe(self):
        sql = self.sql["014_testing_auth_bridge.sql"]
        for token in (
            "create table if not exists public.testing_auth_challenges",
            "enable row level security",
            "revoke all on table public.testing_auth_challenges from public, anon, authenticated",
            "security definer set search_path = ''",
            "mathai_testing_auth_prepare",
            "mathai_testing_auth_reveal",
            "mathai_testing_auth_fail",
            "mathai_testing_auth_consume",
            "mathai_testing_auth_email_hook",
            "grant execute on function public.mathai_testing_auth_reveal(text,text) to anon",
            "grant execute on function public.mathai_testing_auth_consume(text,text) to authenticated",
            "revoke execute on function public.mathai_testing_auth_prepare(text,text,timestamptz) from service_role;",
            "revoke execute on function public.mathai_testing_auth_reveal(text,text) from service_role;",
            "revoke execute on function public.mathai_testing_auth_fail(text,text) from service_role;",
            "revoke execute on function public.mathai_testing_auth_consume(text,text) from service_role;",
            "revoke execute on function public.mathai_testing_auth_email_hook(jsonb) from service_role;",
            "consumed_at is null",
            "expires_at > pg_catalog.now()",
            "attempt_count < 5",
            "jason601226@gmail.com",
            "jason621226@gmail.com",
            "jason671226@gmail.com",
            "expires_at timestamptz not null",
            "attempt_count integer not null default 0",
        ):
            self.assertIn(token, sql)
        normalized = " ".join(sql.lower().split())
        for forbidden in (
            "grant select on public.testing_auth_challenges",
            "grant insert on public.testing_auth_challenges",
            "grant update on public.testing_auth_challenges",
            "consume(text,text) to anon",
            "disable row level security",
            "insert into auth.users",
            "update auth.users",
            "delete from auth.users",
            "to service_role",
            "sign_in_with_password",
        ):
            self.assertNotIn(forbidden, normalized)

    def test_production_testing_auth_bridge_grants_match_consume_contract(self):
        sql = Path("migrations/production/005_testing_auth_bridge.sql").read_text(
            encoding="utf-8"
        )
        for token in (
            "security definer set search_path = ''",
            "grant execute on function public.mathai_testing_auth_consume(text,text) to authenticated",
            "and challenge_hash = p_challenge_hash",
            "consumed_at is null",
            "expires_at > pg_catalog.now()",
            "attempt_count < 5",
        ):
            self.assertIn(token, sql)
        normalized = " ".join(sql.lower().split())
        for forbidden in (
            "consume(text,text) to anon",
            "to service_role",
            "sign_in_with_password",
        ):
            self.assertNotIn(forbidden, normalized)

    def test_testing_auth_function_signatures_are_consistent(self):
        sources = (
            self.sql["014_testing_auth_bridge.sql"],
            Path("migrations/production/005_testing_auth_bridge.sql").read_text(
                encoding="utf-8"
            ),
        )
        for source in sources:
            for token in (
                "create or replace function public.mathai_testing_auth_prepare(",
                "p_email text,",
                "p_challenge_hash text,",
                "p_expires_at timestamptz",
                "revoke all on function public.mathai_testing_auth_prepare(text,text,timestamptz) from public, anon, authenticated;",
                "grant execute on function public.mathai_testing_auth_prepare(text,text,timestamptz) to anon;",
                "revoke all on function public.mathai_testing_auth_reveal(text,text) from public, anon, authenticated;",
                "grant execute on function public.mathai_testing_auth_reveal(text,text) to anon;",
                "revoke all on function public.mathai_testing_auth_fail(text,text) from public, anon, authenticated;",
                "grant execute on function public.mathai_testing_auth_fail(text,text) to anon;",
                "revoke all on function public.mathai_testing_auth_consume(text,text) from public, anon, authenticated;",
                "grant execute on function public.mathai_testing_auth_consume(text,text) to authenticated;",
                "revoke all on function public.mathai_testing_auth_email_hook(jsonb) from public, anon, authenticated;",
                "grant execute on function public.mathai_testing_auth_email_hook(jsonb) to supabase_auth_admin;",
                "revoke execute on function public.mathai_testing_auth_prepare(text,text,timestamptz) from service_role;",
                "revoke execute on function public.mathai_testing_auth_reveal(text,text) from service_role;",
                "revoke execute on function public.mathai_testing_auth_fail(text,text) from service_role;",
                "revoke execute on function public.mathai_testing_auth_consume(text,text) from service_role;",
                "revoke execute on function public.mathai_testing_auth_email_hook(jsonb) from service_role;",
            ):
                self.assertIn(token, source)
            self.assertNotIn("mathai_testing_auth_prepare(text,timestamptz)", source)

    def test_staging_acl_repair_revokes_service_role_only(self):
        sql = self.sql["015_testing_auth_acl_repair.sql"]
        for token in (
            "STAGING ONLY. DO NOT APPLY TO PRODUCTION.",
            "revoke execute on function public.mathai_testing_auth_prepare(text,text,timestamptz) from service_role;",
            "revoke execute on function public.mathai_testing_auth_reveal(text,text) from service_role;",
            "revoke execute on function public.mathai_testing_auth_fail(text,text) from service_role;",
            "revoke execute on function public.mathai_testing_auth_consume(text,text) from service_role;",
            "revoke execute on function public.mathai_testing_auth_email_hook(jsonb) from service_role;",
        ):
            self.assertIn(token, sql)
        normalized = " ".join(sql.lower().split())
        for forbidden in (
            "grant execute",
            "grant all",
            "to anon",
            "to authenticated",
            "create table",
            "drop",
            "delete",
            "truncate",
            "disable row level security",
        ):
            self.assertNotIn(forbidden, normalized)

    def test_teacher_access_student_fk_has_covering_index(self):
        for name in (
            "008_teacher_feedback.sql",
            "009_repair_teacher_feedback_access.sql",
            "010_index_teacher_access_student.sql",
        ):
            sql = self.sql[name]
            self.assertIn("create index if not exists teacher_access_student_idx", sql)
            self.assertIn("on public.teacher_access (student_id, teacher_id)", sql)


if __name__ == "__main__":
    unittest.main()
