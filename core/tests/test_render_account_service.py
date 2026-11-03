import unittest
from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock, patch

from services.render_account_service import RenderAccountService


class TestRenderAccountService(unittest.TestCase):
    def test_calculate_monthly_usage_minutes(self):
        now = datetime.now(UTC)
        current_iso_start = f"{now.year:04d}-{now.month:02d}-02T10:00:00Z"
        current_iso_end = f"{now.year:04d}-{now.month:02d}-02T10:15:00Z"  # 15 mins

        prev_month = 12 if now.month == 1 else now.month - 1
        prev_year = now.year - 1 if now.month == 1 else now.year
        past_iso_start = f"{prev_year:04d}-{prev_month:02d}-15T10:00:00Z"
        past_iso_end = f"{prev_year:04d}-{prev_month:02d}-15T10:45:00Z"  # 45 mins

        deploys = [
            {"deploy": {"createdAt": current_iso_start, "finishedAt": current_iso_end}},
            {"deploy": {"createdAt": past_iso_start, "finishedAt": past_iso_end}},
        ]

        minutes = RenderAccountService.calculate_monthly_usage_minutes(deploys)
        self.assertAlmostEqual(minutes, 15.0, places=1)

    @patch("services.render_account_service.db")
    def test_get_status_overview_fail_closed(self, mock_db):
        mock_db.get_render_account_states.return_value = []
        with patch.object(
            RenderAccountService,
            "get_configured_accounts",
            return_value=[
                {"role": "core", "service_id": "srv-1", "plan": "free", "safe_build_minutes": 450}
            ],
        ):
            overview = RenderAccountService.get_status_overview()
            self.assertFalse(overview["deployment_allowed"])
            self.assertEqual(overview["accounts"][0]["status"], "unknown")

    @patch("services.render_account_service.db")
    def test_get_status_overview_ready(self, mock_db):
        mock_db.get_render_account_states.return_value = [
            {
                "role": "core",
                "account_key": "core",
                "status": "ready",
                "usage_minutes": 120.0,
                "plan": "free",
            }
        ]
        with patch.object(
            RenderAccountService,
            "get_configured_accounts",
            return_value=[
                {"role": "core", "service_id": "srv-1", "plan": "free", "safe_build_minutes": 450}
            ],
        ):
            overview = RenderAccountService.get_status_overview()
            self.assertTrue(overview["deployment_allowed"])
            self.assertEqual(overview["accounts"][0]["status"], "ready")

    @patch("services.render_account_service.db")
    def test_cooldown_recheck_date_set(self, mock_db):
        mock_db.get_render_account_states.return_value = []
        with (
            patch.object(
                RenderAccountService,
                "get_configured_accounts",
                return_value=[
                    {
                        "role": "core",
                        "service_id": "srv-1",
                        "api_key_env": "TEST_KEY",
                        "plan": "free",
                        "safe_build_minutes": 450,
                    }
                ],
            ),
            patch.dict("os.environ", {"TEST_KEY": "dummy_secret"}),
            patch("services.render_account_service.render_get_json", return_value=[]),
            patch.object(
                RenderAccountService, "calculate_monthly_usage_minutes", return_value=460.0
            ),
        ):
            res = RenderAccountService.refresh_account_status("core")
            self.assertEqual(res["status"], "cooldown")
            self.assertEqual(res["reason"], "build_time_limit")
            self.assertIsNotNone(res["recheck_at"])


if __name__ == "__main__":
    unittest.main()
