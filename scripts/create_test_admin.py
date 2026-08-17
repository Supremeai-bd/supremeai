import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore, auth
from loguru import logger

cred = credentials.Certificate("backend/service-account.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# বাংলা মন্তব্য: P0 Fix — হার্ডকোডেড সুপার-অ্যাডমিন পাসওয়ার্ড ও ইমেইল দূর করা হলো।
app_env = os.getenv("APP_ENV", "development").lower()
email = os.getenv("TEST_ADMIN_EMAIL")
password = os.getenv("TEST_ADMIN_PASSWORD")

if app_env == "production":
    if not email or not password:
        logger.critical("Production admin creation requires both TEST_ADMIN_EMAIL and TEST_ADMIN_PASSWORD env vars.")
        sys.exit(1)
else:
    # লোকাল ডেভ এনভায়রনমেন্ট বা কন্টেইনারে সিম্পল সিড টেস্টের জন্য নিরাপদ ডিফল্ট
    email = email or "admin@supremeai.local"
    password = password or "DefaultLocalDevPassword123!"

try:
    # 1. Firebase Auth-এ ইউজার ক্রিয়েট বা গেট করা
    try:
        user = auth.create_user(
            email=email,
            password=password,
            email_verified=True
        )
        logger.success(f"Created user in Auth: {user.uid}")
    except auth.EmailAlreadyExistsError:
        user = auth.get_user_by_email(email)
        logger.info(f"User already exists in Auth: {user.uid}")

    # 2. Firestore-এ অ্যাডমিন রোল সেট করা
    db.collection("admin_users").document(user.uid).set({
        "email": email,
        "role": "admin",
        "created_at": "2026-06-22",
        "totp_secret": None
    }, merge=True)
    logger.success(f"Admin role set in Firestore for {email}")

except Exception as e:
    logger.error(f"Error creating test admin: {e}")
