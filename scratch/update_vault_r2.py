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
doc_ref.set({
    "R2_ACCOUNT_ID": "9d13b864a51306efc2f50c331ba2afac",
    "R2_ACCESS_KEY": "e5c7b9dee4dc351ebc9914173a0652bb",
    "R2_SECRET_KEY": "18631942e31c188c8a109d10e5be64b7754d5b4b524e66937fc1a6830b8f2477",
    "R2_BUCKET_NAME": "supremeai-db-backups"
}, merge=True)
print("Updated R2 secrets in primary_vault!")
