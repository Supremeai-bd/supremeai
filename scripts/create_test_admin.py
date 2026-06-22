import firebase_admin
from firebase_admin import credentials, firestore, auth

cred = credentials.Certificate("backend/service-account.json")
firebase_admin.initialize_app(cred)

db = firestore.client()
email = "testadmin@supremeai.com"
password = "SecurePassword123!"

try:
    # 1. Firebase Auth-এ ইউজার ক্রিয়েট বা গেট করা
    try:
        user = auth.create_user(
            email=email,
            password=password,
            email_verified=True
        )
        print(f"Created user in Auth: {user.uid}")
    except auth.EmailAlreadyExistsError:
        user = auth.get_user_by_email(email)
        print(f"User already exists in Auth: {user.uid}")

    # 2. Firestore-এ অ্যাডমিন রোল সেট করা
    db.collection("admin_users").document(user.uid).set({
        "email": email,
        "role": "admin",
        "created_at": "2026-06-22",
        "totp_secret": None
    }, merge=True)
    print(f"[OK] Admin role set in Firestore for {email}")

except Exception as e:
    print(f"Error: {e}")
