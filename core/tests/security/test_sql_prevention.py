import asyncio

from core.security.injections.sql_prevention import (
    InputSanitizer,
    ParameterizedQueryBuilder,
    QueryInspector,
    SQLAuditor,
    is_safe_query,
    safe_execute,
)


class TestInputSanitizerString:
    def test_truncates_to_max_length(self):
        value = "a" * 2000
        result = InputSanitizer.sanitize_string(value, max_length=10)
        assert len(result) == 10

    def test_removes_null_bytes(self):
        assert "\x00" not in InputSanitizer.sanitize_string("ab\x00cd")

    def test_removes_control_chars(self):
        assert "\x01" not in InputSanitizer.sanitize_string("a\x01b\x1fc")

    def test_non_string_converted(self):
        result = InputSanitizer.sanitize_string(123)
        assert result == "123"

    def test_keeps_clean_string(self):
        assert InputSanitizer.sanitize_string("hello world") == "hello world"


class TestInputSanitizerIdentifier:
    def test_allows_alnum_underscore(self):
        assert InputSanitizer.sanitize_identifier("valid_name_1") == "valid_name_1"

    def test_strips_invalid_chars(self):
        assert InputSanitizer.sanitize_identifier("col; DROP --") == "colDROP"

    def test_empty_raises(self):
        try:
            InputSanitizer.sanitize_identifier("!!!")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(f"Silenced error: {e}")
        else:
            raise AssertionError("expected ValueError for identifier with no valid chars")

    def test_none_raises(self):
        try:
            InputSanitizer.sanitize_identifier("")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(f"Silenced error: {e}")
        else:
            raise AssertionError("expected ValueError for empty identifier")


class TestInputSanitizerInjection:
    def test_detects_drop(self):
        assert InputSanitizer.contains_sql_injection("DROP TABLE users") is True

    def test_detects_union(self):
        assert InputSanitizer.contains_sql_injection("x' UNION SELECT") is True

    def test_detects_tautology(self):
        assert InputSanitizer.contains_sql_injection("' OR 1=1") is True

    def test_detects_comment(self):
        assert InputSanitizer.contains_sql_injection("foo -- bar") is True

    def test_clean_input_false(self):
        assert InputSanitizer.contains_sql_injection("just a normal name") is False

    def test_non_string_false(self):
        assert InputSanitizer.contains_sql_injection(123) is False


class TestInputSanitizerNumeric:
    def test_int_passthrough(self):
        assert InputSanitizer.sanitize_numeric(5) == 5

    def test_float_passthrough(self):
        assert InputSanitizer.sanitize_numeric(2.5) == 2.5

    def test_string_to_float(self):
        assert InputSanitizer.sanitize_numeric("3.5") == 3.5

    def test_invalid_uses_default(self):
        assert InputSanitizer.sanitize_numeric("abc", default=7) == 7


class TestInputSanitizerBoolean:
    def test_bool_passthrough(self):
        assert InputSanitizer.sanitize_boolean(True) is True
        assert InputSanitizer.sanitize_boolean(False) is False

    def test_string_true(self):
        assert InputSanitizer.sanitize_boolean("yes") is True
        assert InputSanitizer.sanitize_boolean("TRUE") is True

    def test_string_false(self):
        assert InputSanitizer.sanitize_boolean("no") is False

    def test_int_nonzero(self):
        assert InputSanitizer.sanitize_boolean(1) is True
        assert InputSanitizer.sanitize_boolean(0) is False


class TestParameterizedQueryBuilder:
    def test_build_select_all(self):
        query, params = ParameterizedQueryBuilder.build_select("users")
        assert query == "SELECT * FROM users"
        assert params == []

    def test_build_select_columns(self):
        query, params = ParameterizedQueryBuilder.build_select("users", ["id", "name"])
        assert query.startswith("SELECT id, name FROM users")
        assert params == []

    def test_build_select_where_eq(self):
        query, params = ParameterizedQueryBuilder.build_select("users", where={"id": 5})
        assert "WHERE id = ?" in query
        assert params == [5]

    def test_build_select_where_in(self):
        query, params = ParameterizedQueryBuilder.build_select("users", where={"id": [1, 2]})
        assert "id IN (?, ?)" in query
        assert params == [1, 2]

    def test_build_select_where_null(self):
        query, params = ParameterizedQueryBuilder.build_select("users", where={"deleted_at": None})
        assert "deleted_at IS NULL" in query
        assert params == []

    def test_build_select_order_limit_offset(self):
        query, params = ParameterizedQueryBuilder.build_select(
            "users", order_by="created_at DESC", limit=10, offset=20
        )
        assert "ORDER BY created_at DESC" in query
        assert "LIMIT ?" in query
        assert "OFFSET ?" in query
        assert params == [10, 20]

    def test_build_insert(self):
        query, params = ParameterizedQueryBuilder.build_insert("users", {"name": "bob", "age": 30})
        assert query == "INSERT INTO users (name, age) VALUES (?, ?)"
        assert params == ["bob", 30]

    def test_build_update(self):
        query, params = ParameterizedQueryBuilder.build_update("users", {"name": "x"}, {"id": 1})
        assert "SET name = ?" in query
        assert "WHERE id = ?" in query
        assert params == ["x", 1]

    def test_build_delete(self):
        query, params = ParameterizedQueryBuilder.build_delete("users", {"id": 1})
        assert query == "DELETE FROM users WHERE id = ?"
        assert params == [1]

    def test_sanitizes_table_identifier(self):
        # sanitize_identifier strips symbols (;, space) but keeps alphanumeric
        # substrings — this matches the documented contract in
        # TestInputSanitizerIdentifier.test_strips_invalid_chars ("col; DROP --"
        # -> "colDROP"). The result "usersDROPTABLEx" has no SQL syntax left
        # (no semicolons/spaces to break out of the identifier position), so it
        # is not executable as injected SQL even though the letters remain.
        query, _ = ParameterizedQueryBuilder.build_select("users; DROP TABLE x")
        assert ";" not in query
        assert "usersDROPTABLEx" in query


class TestQueryInspector:
    def test_safe_query_no_issues(self):
        assert QueryInspector.inspect_sql_statement("SELECT * FROM users WHERE id = ?") == []

    def test_detects_concatenation(self):
        issues = QueryInspector.inspect_sql_statement("'SELECT ' + col")
        assert any(i["type"] == "STRING_CONCATENATION" for i in issues)

    def test_detects_comment(self):
        issues = QueryInspector.inspect_sql_statement("SELECT 1 -- comment")
        assert any(i["type"] == "COMMENT_INJECTION" for i in issues)

    def test_is_safe_query(self):
        assert is_safe_query("SELECT * FROM users WHERE id = ?") is True
        assert is_safe_query("SELECT 1 -- x") is False


class TestSafeExecute:
    def test_sanitizes_string_params(self):
        calls = {}

        class FakeCursor:
            def execute(self, sql, params):
                calls["sql"] = sql
                calls["params"] = params
                return "ok"

        result = safe_execute(FakeCursor(), "UPDATE t SET c = ?", ("bad\x00val",))
        assert result == "ok"
        assert "\x00" not in calls["params"][0]

    def test_passes_through_without_params(self):
        captured = {}

        class FakeCursor:
            def execute(self, sql, params):
                captured["sql"] = sql
                captured["params"] = params
                return None

        safe_execute(FakeCursor(), "SELECT 1")
        assert captured["sql"] == "SELECT 1"
        assert captured["params"] is None


class TestSQLAuditor:
    def test_compiles_patterns(self):
        auditor = SQLAuditor()
        assert len(auditor.compiled_patterns) > 0

    def test_audit_finds_concatenation(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text("cursor.execute('SELECT * FROM t WHERE x = ' + y)\n")
        findings = SQLAuditor().audit_file(f)
        assert any(finding.severity in ("high", "critical") for finding in findings)
