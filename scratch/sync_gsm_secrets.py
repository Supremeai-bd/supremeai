import firebase_admin
from firebase_admin import credentials, firestore
import google.auth
from google.cloud import secretmanager
import os
import json

def main():
    # Load service-account JSON safely by bypassing header comments
    sa_path = "backend/service-account.json"
    if os.path.exists(sa_path):
        with open(sa_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Find start of JSON structure
        json_lines = []
        started = False
        for line in lines:
            if line.strip().startswith("{"):
                started = True
            if started:
                json_lines.append(line)
        json_content = "".join(json_lines)
        
        try:
            cert_dict = json.loads(json_content)
            cred = credentials.Certificate(cert_dict)
            firebase_admin.initialize_app(cred)
            print("Initialized Firebase via service-account.json")
        except Exception as err:
            print(f"Error parsing resolved JSON: {err}")
            firebase_admin.initialize_app()
            print("Fallback initialized Firebase via ADC")
    else:
        firebase_admin.initialize_app()
        print("Initialized Firebase via ADC")

    db = firestore.client()

    # 2. Fetch Vault
    doc_ref = db.collection("system_secrets").document("primary_vault")
    doc = doc_ref.get()
    if not doc.exists:
        print("Error: primary_vault document not found in Firestore system_secrets collection")
        return
    
    vault = doc.to_dict()
    print("Fetched secret vault from Firestore.")

    # 3. Initialize Secret Manager Client
    gcp_project = os.getenv("GCP_PROJECT_ID") or "supremeai-a"
    sm_client = secretmanager.SecretManagerServiceClient()

    keys_to_sync = [
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
        "NVIDIA_API_KEY",
        "FIRECRAWL_API_KEY",
        "HF_API_KEY"
    ]

    for key in keys_to_sync:
        val = None
        for vk, vv in vault.items():
            if vk.upper() == key:
                val = vv
                break
        
        if not val:
            print(f"Skipping {key}: Not found in Firestore primary_vault.")
            continue
        
        if val == "dummy-value" or not str(val).strip():
            print(f"Skipping {key}: Vault has dummy/empty value.")
            continue

        secret_path = f"projects/{gcp_project}/secrets/{key}"
        payload = str(val).strip().encode("UTF-8")
        
        try:
            response = sm_client.add_secret_version(
                request={"parent": secret_path, "payload": {"data": payload}}
            )
            print(f"Successfully synced real key for {key} to Secret Manager (version: {response.name.split('/')[-1]}).")
        except Exception as e:
            print(f"Failed to write secret {key} to Secret Manager: {str(e)}")

if __name__ == "__main__":
    main()
