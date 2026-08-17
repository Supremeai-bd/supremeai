"""SupremeAI 2.0 — App Isolation Tests.

বাংলা মন্তব্য: এই টেস্ট ফাইলটি নিশ্চিত করে যে User API ও Admin API সম্পূর্ণভাবে বিচ্ছিন্ন।
test_rbac.py শুধু RBAC unit-লজিক দেখে, CORS/router আইসোলেশন দেখে না — এই ফাইল সেই ঘাটতি পূরণ করে।

গুরুত্বপূর্ণ: ENV=test/local-এ app_user.py / app_admin.py-এর production CORS guard চলে না
(এবং USER_CORS_ORIGINS/ADMIN_CORS_ORIGINS সাধারণত খালি থাকে)। তাই নীতিটি deterministic ভাবে
যাচাই করতে core/cors_policy.py-এর pure function গুলো সরাসরি টেস্ট করা হয়, আর তার পাশাপাশি
বাস্তব app object-এ cross-portal origin leak হয়নি সেটিও যাচাই করা হয়।
"""

from __future__ import annotations

from core.cors_policy import (
    ADMIN_ORIGIN_DENYLIST,
    USER_ORIGIN_DENYLIST,
    resolve_admin_cors_origins,
    resolve_user_cors_origins,
)

ADMIN_CONSOLE_ORIGIN = "https://supremeai-admin.web.app"
USER_FRONTEND_ORIGINS = {
    "https://supremeai-a.web.app",
    "https://supremeai-studio.vercel.app",
    "https://supremeai-lac.vercel.app",
}


def _get_cors_origins(app) -> list[str]:
    """FastAPI app object থেকে CORSMiddleware-এর allow_origins বের করা।"""
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            kwargs = dict(getattr(middleware, "kwargs", {}) or {})
            return list(kwargs.get("allow_origins", []) or [])
    return []


class TestUserCorsPolicy:
    """resolve_user_cors_origins() — ইউজার ব্যাকএন্ডের CORS নীতি।"""

    def test_admin_console_origin_is_stripped(self):
        """অ্যাডমিন কনসোল origin env var-এ থাকলেও User CORS-এ ঢুকবে না।"""
        resolved = resolve_user_cors_origins(
            ["https://supremeai-lac.vercel.app", ADMIN_CONSOLE_ORIGIN],
        )
        assert ADMIN_CONSOLE_ORIGIN not in resolved, f"User CORS-এ admin console origin leak: {resolved}"

    def test_all_admin_surface_origins_are_stripped(self):
        resolved = resolve_user_cors_origins(["https://supremeai-lac.vercel.app", *ADMIN_ORIGIN_DENYLIST])
        leaked = set(resolved) & ADMIN_ORIGIN_DENYLIST
        assert not leaked, f"User CORS-এ admin origin leak: {leaked}"

    def test_wildcard_is_stripped(self):
        resolved = resolve_user_cors_origins(["*", "https://supremeai-lac.vercel.app"])
        assert "*" not in resolved, "User CORS-এ wildcard (*) পাওয়া গেছে — নিরাপত্তা ঝুঁকি!"

    def test_empty_config_falls_back_to_safe_user_defaults(self):
        """খালি হলে boot crash নয় — নিরাপদ user ডিফল্ট বসবে, তবু admin origin ছাড়াই।"""
        resolved = resolve_user_cors_origins([])
        assert resolved, "খালি কনফিগে User CORS ডিফল্ট বসেনি — production boot crash হতে পারে!"
        assert ADMIN_CONSOLE_ORIGIN not in resolved
        assert "https://supremeai-lac.vercel.app" in resolved, "User CORS ডিফল্টে Vercel domain নেই!"

    def test_wildcard_only_config_falls_back_to_defaults(self):
        resolved = resolve_user_cors_origins(["*"])
        assert "*" not in resolved
        assert "https://supremeai-studio.vercel.app" in resolved

    def test_unused_backup_origin_not_in_defaults(self):
        """অব্যবহৃত backup সার্ভিস origin (08zd) ডিফল্ট তালিকা থেকে সরানো হয়েছে।"""
        resolved = resolve_user_cors_origins([])
        assert "https://supremeai-backend-08zd.onrender.com" not in resolved


class TestAdminCorsPolicy:
    """resolve_admin_cors_origins() — অ্যাডমিন ব্যাকএন্ডের CORS নীতি।"""

    def test_user_origins_are_stripped(self):
        """ইউজার frontend origin misconfigured env থেকে এলেও Admin CORS-এ থাকবে না।"""
        resolved = resolve_admin_cors_origins([ADMIN_CONSOLE_ORIGIN, *USER_FRONTEND_ORIGINS])
        leaked = USER_FRONTEND_ORIGINS & set(resolved)
        assert not leaked, f"Admin CORS-এ user origins leak: {leaked}"

    def test_full_user_denylist_is_stripped(self):
        resolved = resolve_admin_cors_origins(list(USER_ORIGIN_DENYLIST))
        leaked = USER_ORIGIN_DENYLIST & set(resolved)
        assert not leaked, f"Admin CORS-এ denylisted user origins leak: {leaked}"

    def test_wildcard_is_stripped(self):
        resolved = resolve_admin_cors_origins(["*"])
        assert "*" not in resolved, "Admin CORS-এ wildcard (*) পাওয়া গেছে — নিরাপত্তা ঝুঁকি!"

    def test_admin_console_origin_always_present(self):
        """self-healing guard — খালি বা ভুল কনফিগেও admin console origin থাকবে (preflight 403/500 রোধ)।"""
        assert ADMIN_CONSOLE_ORIGIN in resolve_admin_cors_origins([])
        assert ADMIN_CONSOLE_ORIGIN in resolve_admin_cors_origins(["*"])
        assert ADMIN_CONSOLE_ORIGIN in resolve_admin_cors_origins(list(USER_FRONTEND_ORIGINS))

    def test_no_duplicate_origins(self):
        resolved = resolve_admin_cors_origins([ADMIN_CONSOLE_ORIGIN, ADMIN_CONSOLE_ORIGIN])
        assert len(resolved) == len(set(resolved)), f"Admin CORS-এ ডুপ্লিকেট origin: {resolved}"


class TestAdminAppIsolation:
    """বাস্তব Admin FastAPI app object — configured origin leak যাচাই।"""

    def test_admin_cors_does_not_allow_user_origins(self):
        from core.app_admin import app

        origins = _get_cors_origins(app)
        leaked = USER_ORIGIN_DENYLIST & set(origins)
        assert not leaked, f"Admin CORS-এ user origins leak: {leaked}"

    def test_admin_cors_is_wildcard_free(self):
        from core.app_admin import app

        origins = _get_cors_origins(app)
        assert "*" not in origins, "Admin CORS-এ wildcard (*) পাওয়া গেছে — নিরাপত্তা ঝুঁকি!"


class TestUserAppIsolation:
    """বাস্তব User FastAPI app object — admin surface leak যাচাই।"""

    def test_user_cors_does_not_allow_admin_console(self):
        from core.app_user import app

        origins = _get_cors_origins(app)
        leaked = ADMIN_ORIGIN_DENYLIST & set(origins)
        assert not leaked, f"User CORS-এ admin origin পাওয়া গেছে — isolation ভাঙা: {leaked}"

    def test_user_cors_is_wildcard_free(self):
        from core.app_user import app

        origins = _get_cors_origins(app)
        assert "*" not in origins, "User CORS-এ wildcard (*) পাওয়া গেছে!"

    def test_no_admin_routes_in_user_app(self):
        """ইউজার API-তে /admin-api বা admin-dashboard route থাকবে না।"""
        from core.app_user import app

        paths = {getattr(r, "path", "") for r in app.routes}
        admin_leaked = [p for p in paths if "/admin-api" in p or p.startswith("/admin-dashboard")]
        assert not admin_leaked, f"User app-এ admin routes পাওয়া গেছে: {admin_leaked}"


class TestTrustedOriginIsolation:
    """TrustedOriginMiddleware — server-side origin allowlist-ও portal-ভিত্তিক কিনা।

    বাংলা মন্তব্য: শুধু CORSMiddleware ঠিক করলে যথেষ্ট নয় — এই middleware OPTIONS preflight
    সরাসরি ইন্টারসেপ্ট করে Access-Control-Allow-Origin ফেরত দেয়। আগে এটি user+admin উভয়
    origin একসাথে ট্রাস্ট করত, ফলে আইসোলেশন ভেঙে যেত।
    """

    def test_user_instance_rejects_admin_console_origin(self):
        from core.security.origin_validator import TrustedOriginMiddleware

        origins = TrustedOriginMiddleware(app=None, portal_role="user").allowed_origins
        leaked = ADMIN_ORIGIN_DENYLIST & set(origins)
        assert not leaked, f"User instance-এর trusted origin-এ admin origin leak: {leaked}"

    def test_admin_instance_rejects_user_origins(self):
        from core.security.origin_validator import TrustedOriginMiddleware

        origins = TrustedOriginMiddleware(app=None, portal_role="admin").allowed_origins
        leaked = USER_ORIGIN_DENYLIST & set(origins)
        assert not leaked, f"Admin instance-এর trusted origin-এ user origin leak: {leaked}"

    def test_admin_instance_keeps_admin_console_origin(self):
        from core.security.origin_validator import TrustedOriginMiddleware

        origins = TrustedOriginMiddleware(app=None, portal_role="admin").allowed_origins
        assert ADMIN_CONSOLE_ORIGIN in origins, "Admin instance-এ admin console origin নেই — panel ব্লক হবে!"

    def test_portal_role_defaults_to_service_role(self):
        """বাংলা: SERVICE_ROLE দিয়েই main.py app_user/app_admin বেছে নেয় — দুটো সিঙ্কে থাকতে হবে।"""
        from core.security.origin_validator import TrustedOriginMiddleware

        assert TrustedOriginMiddleware(app=None).portal_role in {"user", "admin"}


class TestRouterIsolation:
    """USER_ROUTERS / ADMIN_ROUTERS তালিকা-স্তরের বিচ্ছিন্নতা।"""

    def test_user_routers_exclude_admin_paths(self):
        from api.routers import USER_ROUTERS, _admin_paths

        user_mod_names = {mod for mod, _ in USER_ROUTERS}
        leaked_admin = user_mod_names & _admin_paths
        assert not leaked_admin, f"Admin routes user-এ leak: {leaked_admin}"

    def test_admin_routers_contain_required_routes(self):
        from api.routers import ADMIN_ROUTERS

        admin_mods = {mod for mod, _ in ADMIN_ROUTERS}
        required = {"api.routes.health", "api.routes.admin", "api.routes.admin_dashboard"}
        missing = required - admin_mods
        assert not missing, f"Admin routers-এ required routes নেই: {missing}"

    def test_llm_gateway_is_admin_only(self):
        """llm_gateway (/api/admin/llm/*) শুধুমাত্র Admin API-তে থাকবে।"""
        from api.routers import ADMIN_ROUTERS, USER_ROUTERS

        assert "api.routes.llm_gateway" not in {mod for mod, _ in USER_ROUTERS}
        assert "api.routes.llm_gateway" in {mod for mod, _ in ADMIN_ROUTERS}
