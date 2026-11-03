import time
from unittest.mock import patch

from tools.social.viral_referral_engine import ViralReferralEngine


class TestViralReferralEngine:
    def setup_method(self):
        self.engine = ViralReferralEngine()

    def test_generate_referral_code_format(self):
        with patch.dict(
            "os.environ", {"STAGING_REPLICA_URL": "http://localhost:8000"}
        ):  # is_local()
            result = self.engine.generate_referral_code("user-123")
        assert result["status"] == "success"
        assert result["code"].startswith("SUPREME-")
        assert len(result["code"]) == len("SUPREME-") + 8
        assert result["expires_at"] > time.time()

    def test_generate_referral_code_unique(self):
        with patch.dict(
            "os.environ", {"STAGING_REPLICA_URL": "http://localhost:8000"}
        ):  # is_local()
            code1 = self.engine.generate_referral_code("user-1")["code"]
            code2 = self.engine.generate_referral_code("user-2")["code"]
        assert code1 != code2

    def test_reward_tiers_bronze(self):
        with patch.object(
            self.engine,
            "_calculate_reward",
            return_value={"reward": 5.0, "credit_bonus": 10, "tier": "bronze", "count": 1},
        ):
            result = self.engine._calculate_reward("user-123")
            assert result["tier"] == "bronze"
            assert result["credit_bonus"] == 10

    def test_reward_tiers_platinum(self):
        with patch.object(
            self.engine,
            "_calculate_reward",
            return_value={"reward": 50.0, "credit_bonus": 1000, "tier": "platinum", "count": 50},
        ):
            result = self.engine._calculate_reward("user-999")
            assert result["tier"] == "platinum"
            assert result["credit_bonus"] == 1000

    def test_generate_deep_link_twitter(self):
        with patch.dict(
            "os.environ", {"STAGING_REPLICA_URL": "http://localhost:8000"}
        ):  # is_local()
            link = self.engine.generate_deep_link("CODE123", "twitter")
        assert "twitter.com/intent/tweet" in link
        assert "CODE123" in link

    def test_generate_deep_link_whatsapp(self):
        link = self.engine.generate_deep_link("CODE123", "whatsapp")
        assert "api.whatsapp.com" in link
        assert "CODE123" in link

    def test_generate_deep_link_generic_fallback(self):
        link = self.engine.generate_deep_link("CODE123", "unknown")
        assert "CODE123" in link
        assert link.endswith("/invite/CODE123")

    def test_fraud_detection_threshold(self):
        with patch("tools.social.viral_referral_engine.db") as mock_db:
            mock_db.client = None
            result = self.engine._is_fraudulent("u1", "new-u", {"ip_address": "1.2.3.4"})
            assert result is False

    def test_wallet_balance_new_user(self):
        with patch("tools.social.viral_referral_engine.db") as mock_db:
            mock_db.client = None
            balance = self.engine._get_wallet("new-user")
            assert balance["balance"] == 0.0
            assert balance["user_id"] == "new-user"
