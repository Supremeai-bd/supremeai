import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("OPENROUTER_API_KEY", "mock-key-value")
os.environ.setdefault("HF_API_KEY", "")


class TestSSOIntegrator:
    def test_sso_instantiation(self):
        from tools.sso_integrator import SSOIntegrator

        integrator = SSOIntegrator()
        assert integrator.onelogin in (True, False)

    def test_sso_metadata_fallback(self):
        from tools.sso_integrator import SSOIntegrator

        integrator = SSOIntegrator()
        meta = integrator.get_metadata()
        assert "body" in meta

    def test_role_mapping_default(self):
        from tools.sso_integrator import SSOIntegrator

        integrator = SSOIntegrator()
        roles = integrator.map_roles(["Viewers", "Operators"])
        assert "viewer" in roles
        assert "operator" in roles

    def test_role_mapping_empty(self):
        from tools.sso_integrator import SSOIntegrator

        integrator = SSOIntegrator()
        roles = integrator.map_roles([])
        assert roles == ["viewer"]


class TestReferralEngine:
    def test_referral_engine_generates_code(self):
        import database.supabase_client as db_mod
        from tools.social.viral_referral_engine import ViralReferralEngine

        original = db_mod.db.client
        db_mod.db.client = None
        try:
            engine = ViralReferralEngine()
            result = engine.generate_referral_code("user_test")
            assert "code" in result
            assert result["code"].startswith("SUPREME-")
        finally:
            db_mod.db.client = original

    def test_referral_deep_links(self):
        from tools.social.viral_referral_engine import ViralReferralEngine

        engine = ViralReferralEngine()
        link_fb = engine.generate_deep_link("SUPREME-ABC123", "facebook")
        assert "facebook.com/sharer" in link_fb
        link_tw = engine.generate_deep_link("SUPREME-ABC123", "twitter")
        assert "twitter.com/intent" in link_tw

    def test_wallet_balance_default(self):
        import database.supabase_client as db_mod
        from tools.social.viral_referral_engine import ViralReferralEngine

        original = db_mod.db.client
        db_mod.db.client = None
        try:
            engine = ViralReferralEngine()
            result = engine.get_wallet_balance("nonexistent_user")
            assert result["balance"] == 0.0
        finally:
            db_mod.db.client = original


class TestTenantRateLimiter:
    def test_rate_limiter_init(self):
        from tools.tenant_rate_limiter import TenantRateLimiter

        limiter = TenantRateLimiter(redis_client=None)
        assert limiter.billing_tiers["free"]["rpm"] == 60

        from tools.tenant_rate_limiter import TenantRateLimiter

        limiter = TenantRateLimiter(redis_client=None)
        assert "pro" in limiter.billing_tiers
        assert "enterprise" in limiter.billing_tiers
