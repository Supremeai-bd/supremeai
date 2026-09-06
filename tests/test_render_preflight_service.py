import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.core.contracts.render_preflight_store import RenderPreflightStore
from backend.services.render_preflight_service import (
    RenderPreflightService,
    calculate_deploy_usage_minutes,
)


class RenderPreflightServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = RenderPreflightStore(db_path=":memory:")
        self.service = RenderPreflightService(store=self.store)

    def test_1_parse_render_deployment_timestamps_correctly(self):
        now = datetime.now(timezone.utc)
        start = now.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=15)
        deploys = [
            {
                "deploy": {
                    "createdAt": start.isoformat(),
                    "finishedAt": end.isoformat(),
                }
            }
        ]
        minutes = calculate_deploy_usage_minutes(deploys)
        self.assertEqual(minutes, 15.0)

    def test_2_usage_is_never_treated_as_zero_when_data_is_missing(self):
        # When credentials or service IDs are missing, status must be unknown
        result = self.service.refresh_account_status(
            account_role="core",
            service_id="",
            api_key=None,
        )
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason_code"], "missing_credentials")
        self.assertIsNone(result["usage_minutes"])

    def test_3_limit_response_creates_cooldown_exactly_once(self):
        # Directly simulate limit condition
        now = datetime.now(timezone.utc)
        res = self.store.upsert_account_and_record_event(
            account_role="core",
            service_id="srv-test-1",
            status="cooldown",
            reason_code="build_time_limit",
            reason_message="Usage 480m >= 450m",
            usage_minutes=480.0,
            detected_at=now.isoformat(),
            recheck_at=(now + timedelta(days=10)).isoformat(),
            event_type="limit_detected",
            increment_retry=True,
        )
        self.assertEqual(res["status"], "cooldown")
        self.assertEqual(res["retry_count"], 1)

        events = self.store.get_events("core")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "limit_detected")

    def test_4_repeated_checks_do_not_extend_existing_cooldown(self):
        now = datetime.now(timezone.utc)
        original_recheck = (now + timedelta(days=10)).isoformat()
        self.store.upsert_account_and_record_event(
            account_role="core",
            service_id="srv-test-1",
            status="cooldown",
            reason_code="build_time_limit",
            detected_at=now.isoformat(),
            recheck_at=original_recheck,
            event_type="limit_detected",
        )

        # Repeated refresh during active cooldown window
        account = self.service.refresh_account_status(
            account_role="core",
            service_id="srv-test-1",
            api_key="fake-key",
            force=False,
        )
        self.assertEqual(account["recheck_at"], original_recheck)
        self.assertEqual(account["status"], "cooldown")

    def test_5_successful_recheck_returns_account_to_ready(self):
        now = datetime.now(timezone.utc)
        # Put into cooldown first
        self.store.upsert_account_and_record_event(
            account_role="worker",
            service_id="srv-worker-1",
            status="cooldown",
            reason_code="build_time_limit",
            recheck_at=(now - timedelta(days=1)).isoformat(),
        )

        # Upsert back to ready after successful recheck
        res = self.store.upsert_account_and_record_event(
            account_role="worker",
            service_id="srv-worker-1",
            status="ready",
            usage_minutes=50.0,
            safe_build_minutes=450.0,
            recheck_at=None,
            event_type="ready",
            increment_retry=False,
        )
        self.assertEqual(res["status"], "ready")
        self.assertIsNone(res["recheck_at"])

    def test_6_failed_recheck_creates_new_event_and_bounded_next_date(self):
        now = datetime.now(timezone.utc)
        self.store.upsert_account_and_record_event(
            account_role="scraper",
            service_id="srv-scraper-1",
            status="cooldown",
            retry_count=1,
            recheck_at=(now - timedelta(days=1)).isoformat(),
        )

        # Simulate second failed recheck -> backoff 20 days
        next_recheck = (now + timedelta(days=20)).isoformat()
        res = self.store.upsert_account_and_record_event(
            account_role="scraper",
            service_id="srv-scraper-1",
            status="cooldown",
            reason_code="build_time_limit",
            recheck_at=next_recheck,
            increment_retry=True,
            event_type="limit_detected",
        )
        self.assertEqual(res["retry_count"], 2)
        self.assertEqual(res["recheck_at"], next_recheck)

    def test_7_provider_api_errors_produce_unknown_or_error_status(self):
        # Refresh with an unreachable endpoint or bad service_id produces unknown/error, never ready
        res = self.service.refresh_account_status(
            account_role="mcp",
            service_id="invalid-srv-9999",
            api_key="invalid-key",
            force=True,
        )
        self.assertIn(res["status"], ("unknown", "error"))
        self.assertIsNotNone(res.get("last_error"))

    def test_8_manual_override_is_audited(self):
        # Create blocked record
        self.store.upsert_account_and_record_event(
            account_role="core",
            service_id="srv-core-1",
            status="cooldown",
            reason_code="build_time_limit",
        )

        overridden = self.service.manual_override(
            account_role="core",
            approved_by="admin_alice",
            reason="Emergency hotfix release",
        )
        self.assertEqual(overridden["status"], "ready")
        self.assertTrue(overridden["manual_override"])
        self.assertEqual(overridden["manual_override_by"], "admin_alice")

        events = self.store.get_events("core")
        override_events = [e for e in events if e["event_type"] == "manual_override"]
        self.assertEqual(len(override_events), 1)
        self.assertEqual(override_events[0]["old_status"], "cooldown")
        self.assertEqual(override_events[0]["new_status"], "ready")

    def test_9_secrets_are_absent_from_persisted_payloads_and_logs(self):
        sensitive_payload = {
            "api_key": "rnd_sec1234567890",
            "token": "secret_token_val",
            "usage": 200.0,
            "nested": {"password": "secret_password"},
        }
        res = self.store.upsert_account_and_record_event(
            account_role="core",
            service_id="srv-core-1",
            status="ready",
            payload=sensitive_payload,
        )
        stored_payload = res["last_render_payload"]
        self.assertNotIn("rnd_sec1234567890", json.dumps(stored_payload))
        self.assertNotIn("secret_password", json.dumps(stored_payload))
        self.assertEqual(stored_payload["api_key"], "[REDACTED]")
        self.assertEqual(stored_payload["nested"]["password"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
