"""
Firebase Admin Setup Script — One-time run করুন
Firestore-এ niloyjoy7@gmail.com কে admin role দেবে
"""
import firebase_admin
from firebase_admin import credentials, firestore, auth

# 1. Service Account দিয়ে initialize করুন
#    (নিচের path আপনার service-account.json এর path দিন)
cred = credentials.Certificate("backend/service-account.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# 2. niloyjoy7@gmail.com এর UID খোঁজো Firebase Auth থেকে
try:
    user = auth.get_user_by_email("niloyjoy7@gmail.com")
    uid = user.uid
    print(f"Found user: {uid}")
except Exception as e:
    print(f"Error: {e}")
    uid = None

# 3. Firestore-এ admin role set করো
if uid:
    db.collection("admin_users").document(uid).set({
        "email": "niloyjoy7@gmail.com",
        "role": "admin",
        "created_at": "2026-06-22",
        "totp_secret": None,  # প্রথম login-এ TOTP setup হবে
    }, merge=True)
    print(f"[OK] Admin role set for niloyjoy7@gmail.com (uid={uid})")

# 4. admin@supremeai.com কেও admin করো (যদি চান)
try:
    user2 = auth.get_user_by_email("admin@supremeai.com")
    db.collection("admin_users").document(user2.uid).set({
        "email": "admin@supremeai.com",
        "role": "admin",
        "created_at": "2026-06-22",
    }, merge=True)
    print(f"[OK] Admin role set for admin@supremeai.com")
except Exception as e:
    print(f"admin@supremeai.com: {e}")

print("Done! Now restart the backend server.")
