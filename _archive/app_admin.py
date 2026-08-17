"""SupremeAI 2.0 — Admin API entrypoint. Admin dashboard + Anti-Hacking Agent only.

বাংলা মন্তব্য: অ্যাডমিন এপিআই এন্ট্রি পয়েন্ট যা শুধুমাত্র অ্যাডমিন প্যানেল এবং সিকিউরিটি রাউটগুলো এক্সপোজ করে।
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import include_admin_routers
from core.app_builder import build_app_shell, router_health_check
from core.config import settings
from core.cors_policy import USER_ORIGIN_DENYLIST, resolve_admin_cors_origins
from middleware.anti_hacking import AntiHackingContextMiddleware

app: FastAPI = build_app_shell(title="SupremeAI Admin API")

# বাংলা মন্তব্য: ADMIN_CORS_ORIGINS ফাঁকা (empty) বা অসঙ্গতিপূর্ণ থাকলে
# বুট-টাইমে crash/preflight 403 এড়াতে ডিফল্ট অ্যাডমিন origin অটো-পপুলেট করা হচ্ছে।
# শুধুমাত্র অ্যাডমিন কনসোল origin (supremeai-admin.web.app) — Vercel/Netlify user client নয়।
_configured_admin_origins = list(settings.admin_cors_origins or [])
_admin_origins = resolve_admin_cors_origins(_configured_admin_origins)

if _admin_origins != _configured_admin_origins:
    from loguru import logger

    if "*" in _configured_admin_origins:
        logger.warning("⚠️ Admin CORS wildcard detected. Removing '*' and forcing admin console origin.")
    _leaked_user_origins = [o for o in _configured_admin_origins if o in USER_ORIGIN_DENYLIST]
    if _leaked_user_origins:
        logger.warning(f"⚠️ User origin(s) stripped from Admin CORS for isolation: {_leaked_user_origins}")
    if "https://supremeai-admin.web.app" not in _configured_admin_origins:
        logger.warning(
            "⚠️ admin_cors_origins missing admin web console origin — adding it to prevent preflight 403/500."
        )

settings.admin_cors_origins = _admin_origins

# বাংলা মন্তব্য: Anti-Hacking, Cache-Control ও CSRF সিকিউরিটি হেডারগুলোর প্রিফ্লাইট সামলাতে allow_headers=["*"] সেট করা হলো
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.admin_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Anti-Hacking Agent hook — runs before routes, on Admin API only
app.add_middleware(AntiHackingContextMiddleware)

include_admin_routers(app)

# বাংলা মন্তব্য: অ্যাডমিন এপিআইতে ইউজারের মতো ২০টি রাউটার লোড হয় না (কেবল ADMIN_ROUTERS লোড হয়)।
# তাই এখানে মিনিমাম রাউটের উপস্থিতি চেক করা হচ্ছে যাতে প্রসেসটি ক্র্যাশ না করে।
# বাংলা মন্তব্য: preferences রাউটার যোগ হওয়ায় কাউন্ট ৫->৬ আপডেট করা হলো।
router_health_check(app, expected_count=6)
