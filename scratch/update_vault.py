import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

sa_path = "backend/service-account.json"
if os.path.exists(sa_path):
    with open(sa_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    json_lines = []
    started = False
    for line in lines:
        if line.strip().startswith("{"):
            started = True
        if started:
            json_lines.append(line)
    json_content = "".join(json_lines)
    cert_dict = json.loads(json_content)
    cred = credentials.Certificate(cert_dict)
    firebase_admin.initialize_app(cred)
else:
    firebase_admin.initialize_app()

db = firestore.client()
doc_ref = db.collection("system_secrets").document("primary_vault")
doc_ref.set({"SUPABASE_DB_URL": "postgresql://postgres.zxhsevgrdkfvapllqpiw:njel.com.bd1234@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres"}, merge=True)
print("Updated SUPABASE_DB_URL in primary_vault!")
