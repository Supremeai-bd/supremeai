"""specs/001 close-out — configuration contract tests (MASTER_PLAN Phase 1).

বাংলা: এই টেস্টগুলো কনফিগ সিস্টেমের *চুক্তি* লক করে:
  1. server.py-র CORS allow-list অবশ্যই middleware/cors_policy.py resolver দিয়ে
     তৈরি হবে (single source of truth — দুটো সমান্তরাল পথ আর থাকবে না);
  2. wildcard '*' কোনো resolved origin-list-এ বাঁচতে পারবে না;
  3. ConfigValidationReport সৎ হবে — অনুপস্থিত required var = error,
     ভাঙা ফরম্যাট = error, fix suggestion ছাড়া error চলবে না।
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


class TestCorsContract(unittest.TestCase):
    # FINAL-TEST REMOVAL: the previous test inspected api/server.py source
    # text, but server.py (the superseded Phase-4 standalone FastAPI app) was
    # deleted — the real app lives in core/app.py. The CORS contract itself is
    # still enforced by the resolver tests below.
    def test_resolved_allowlist_properties(self):
        """Resolver-সমাহিত allow-list (server.py-র নির্মাণপদ্ধতি) চুক্তি মেনে চলে।"""
        from middleware.cors_policy import resolve_admin_cors_origins, resolve_user_cors_origins

        dev = ["http://localhost:3000", "http://localhost:5173", "tauri://localhost"]
        prod = ["https://app.example.com"]
        admin = ["https://admin.example.com"]
        allowed = set(resolve_user_cors_origins(dev + prod)) | set(
            resolve_admin_cors_origins(admin)
        )
        self.assertNotIn("*", allowed)
        self.assertIn("https://app.example.com", allowed)
        self.assertIn("http://localhost:3000", allowed)  # dev convenience preserved

    def test_resolver_drops_wildcard_and_keeps_explicit(self):
        from middleware.cors_policy import resolve_user_cors_origins

        resolved = resolve_user_cors_origins(
            ["*", "http://localhost:3000", "https://app.example.com"]
        )
        self.assertNotIn("*", resolved)
        self.assertIn("https://app.example.com", resolved)

    def test_admin_resolver_guarantees_required_admin_origins(self):
        import os

        from middleware.cors_policy import resolve_admin_cors_origins

        with patch.dict(
            os.environ, {"ADMIN_CORS_ORIGINS": "https://admin.example.com"}, clear=False
        ):
            # মডিউল-লেভেল কনস্ট্যান্ট আগে লোড হতে পারে — resolver-এর কনট্র্যাক্ট:
            # configured যা-ই হোক, ADMIN_ALLOWED_ORIGINS-এ থাকা origin বাদ পড়ে না
            from middleware import cors_policy as cp

            required = cp.ADMIN_ALLOWED_ORIGINS
            resolved = resolve_admin_cors_origins([])
            for origin in required:
                self.assertIn(origin, resolved)


class TestConfigValidationReportContract(unittest.TestCase):
    def test_report_is_honest_about_missing_secret(self):
        import os

        from core.config_validation import build_config_validation_report

        # Issue #567 (BE-16): canonical name is SUPREMEAI_JWT_SECRET; the
        # JWT_SECRET alias is cleared too so the report must flag the
        # canonical var as missing.
        with patch.dict(os.environ, {"SUPREMEAI_JWT_SECRET": "", "JWT_SECRET": ""}, clear=False):
            report = build_config_validation_report(env="test")
        names = {c.name for c in report.errors}
        self.assertIn("SUPREMEAI_JWT_SECRET", names)
        self.assertFalse(report.ok)

    def test_deprecated_jwt_alias_is_warning_not_error(self):
        import os

        from core.config_validation import build_config_validation_report

        # Issue #567 (BE-16): operators still on the legacy JWT_SECRET name
        # get a deprecation warning, not a false "missing required var" error.
        with patch.dict(
            os.environ,
            {"SUPREMEAI_JWT_SECRET": "", "JWT_SECRET": "legacy-secret-value"},
            clear=False,
        ):
            report = build_config_validation_report(env="test")
        error_names = {c.name for c in report.errors}
        self.assertNotIn("SUPREMEAI_JWT_SECRET", error_names)
        alias_checks = [
            c for c in report.checks if c.name == "SUPREMEAI_JWT_SECRET" and c.status == "warning"
        ]
        self.assertTrue(alias_checks, "expected a deprecation warning for the JWT_SECRET alias")

    def test_every_error_has_fix_suggestion(self):
        from core.config_validation import build_config_validation_report

        report = build_config_validation_report(env="test")
        for err in report.errors:
            self.assertTrue(
                err.fix_suggestion,
                f"error {err.name} without fix suggestion violates the contract",
            )

    def test_report_fields_shape(self):
        from core.config_validation import build_config_validation_report

        report = build_config_validation_report(env="test")
        data = report.model_dump()
        for key in ("environment", "ok", "errors", "warnings", "checks", "generated_at"):
            self.assertIn(key, data)
        self.assertEqual(data["environment"], "test")

    def test_bad_redis_format_is_error(self):
        import os

        from core.config_validation import build_config_validation_report

        with patch.dict(os.environ, {"REDIS_URL": "not-a-redis-url"}, clear=False):
            report = build_config_validation_report(env="test")
        names = {c.name for c in report.errors}
        self.assertIn("REDIS_URL", names)


class TestDeployArtifactContract(unittest.TestCase):
    def test_unsubstituted_placeholder_detected(self):
        """Build validator detects unsubstituted {{USER_BACKEND_URL}} (FR-005, SC-006, T014)."""
        import importlib.util
        import tempfile
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[4]
        validator_script = repo_root / "scripts" / "ci" / "validate_frontend_build.py"
        self.assertTrue(validator_script.exists())

        spec = importlib.util.spec_from_file_location("validate_frontend_build", validator_script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with tempfile.NamedTemporaryFile(
            "w+", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            tf.write('{"destination": "{{USER_BACKEND_URL}}/api"}')
            temp_path = Path(tf.name)

        try:
            violations = mod.scan_file(temp_path)
            self.assertTrue(
                any("unresolved deploy placeholder" in v for v in violations),
                "Unresolved {{USER_BACKEND_URL}} placeholder was not caught by scanner",
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
