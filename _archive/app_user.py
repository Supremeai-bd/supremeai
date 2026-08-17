"""SupremeAI 2.0 — User API entrypoint. Chat/user-facing routes only.

বাংলা মন্তব্য: ইউজার এপিআই এন্ট্রি পয়েন্ট যা শুধুমাত্র চ্যাট ও ইউজার-ফেসিং রাউটগুলো এক্সপোজ করে।
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import include_user_routers
from core.app_builder import build_app_shell, router_health_check
from core.config import settings
from core.cors_policy import ADMIN_ORIGIN_DENYLIST, resolve_user_cors_origins

app: FastAPI = build_app_shell(title="SupremeAI User API")

# বাংলা মন্তব্য: ইউজার ব্যাকএন্ড শুধু Vercel/Netlify ও Firebase user domain থেকে request গ্রহণ করবে।
# admin.web.app (এবং admin Render host) ইচ্ছাকৃতভাবে বাদ — সম্পূর্ণ আর্কিটেকচারাল আইসোলেশন।
# wildcard/খালি হলে boot crash এড়াতে নিরাপদ ডিফল্ট বসানো হয় (resolve_user_cors_origins দেখুন)।
_configured_user_origins = list(settings.user_cors_origins or [])
_resolved_user_origins = resolve_user_cors_origins(_configured_user_origins)

if _resolved_user_origins != _configured_user_origins:
    from loguru import logger

    _dropped = [o for o in _configured_user_origins if o not in _resolved_user_origins]
    if any(o in ADMIN_ORIGIN_DENYLIST for o in _dropped):
        logger.warning(f"⚠️ Admin origin(s) stripped from User CORS for isolation: {_dropped}")
    else:
        logger.warning(
            "⚠️ User CORS wildcard/drift detected. Setting default trusted production origins."
        )

settings.user_cors_origins = _resolved_user_origins

# বাংলা মন্তব্য: Anti-Hacking, Cache-Control ও CSRF সিকিউরিটি হেডারগুলোর প্রিফ্লাইট সামলাতে allow_headers=["*"] সেট করা হলো
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.user_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

include_user_routers(app)
router_health_check(app)
