"""
Unit tests for engine/tools.py – no DB or LLM required.
"""
import pytest

from app.engine.tools import apply_row_level_security, clean_sql, is_safe_sql

ALLOWED = ["students", "schools", "tc", "tc_files", "school_users"]


# ── is_safe_sql ───────────────────────────────────────────────────────────────

class TestIsSafeSql:
    def test_simple_select(self):
        assert is_safe_sql("SELECT * FROM students", ALLOWED)

    def test_join(self):
        sql = "SELECT s.student_name FROM students s JOIN schools sc ON s.udise_code = sc.udise"
        assert is_safe_sql(sql, ALLOWED)

    def test_blocks_drop(self):
        assert not is_safe_sql("DROP TABLE students", ALLOWED)

    def test_blocks_delete(self):
        assert not is_safe_sql("DELETE FROM students WHERE 1=1", ALLOWED)

    def test_blocks_update(self):
        assert not is_safe_sql("UPDATE students SET name='x'", ALLOWED)

    def test_blocks_non_select(self):
        assert not is_safe_sql("SHOW TABLES", ALLOWED)

    def test_blocks_unauthorized_table(self):
        assert not is_safe_sql("SELECT * FROM superadmin_otp", ALLOWED)

    def test_empty_query(self):
        assert not is_safe_sql("", ALLOWED)


# ── apply_row_level_security ──────────────────────────────────────────────────

class TestApplyRLS:
    UDISE = "123456"

    def test_adds_where_to_students(self):
        sql = "SELECT * FROM students"
        result = apply_row_level_security(sql, "super_admin", self.UDISE)
        assert "students.udise_code = '123456'" in result

    def test_appends_and_to_existing_where(self):
        sql = "SELECT * FROM students WHERE grade = 5"
        result = apply_row_level_security(sql, "super_admin", self.UDISE)
        assert "AND" in result
        assert "students.udise_code = '123456'" in result

    def test_adds_where_to_schools(self):
        sql = "SELECT * FROM schools"
        result = apply_row_level_security(sql, "super_admin", self.UDISE)
        assert "schools.udise = '123456'" in result

    def test_no_filter_for_unknown_role(self):
        sql = "SELECT * FROM students"
        result = apply_row_level_security(sql, "viewer", self.UDISE)
        assert result == sql


# ── clean_sql ─────────────────────────────────────────────────────────────────

class TestCleanSql:
    def test_strips_markdown(self):
        raw = "```sql\nSELECT 1\n```"
        assert clean_sql(raw) == "SELECT 1"

    def test_trims_preamble(self):
        raw = "Sure! Here is the query:\nSELECT * FROM schools"
        assert clean_sql(raw).startswith("SELECT")
