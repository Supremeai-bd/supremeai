from infisical_client import ClientSettings, InfisicalClient, AuthenticationOptions, UniversalAuthMethod, CreateSecretOptions, UpdateSecretOptions
from dotenv import dotenv_values
import sys
import json

client_id = '9f2363cf-3cec-43f6-b155-a8625de19250'
client_secret = '***REMOVED***'
project_id = '92aa20c4-aef5-4e33-82bd-efb06058aaf0'

env_vars = dotenv_values('.env')

client = InfisicalClient(ClientSettings(
    auth=AuthenticationOptions(
        universal_auth=UniversalAuthMethod(
            client_id=client_id,
            client_secret=client_secret
        )
    )
))

firebase_json = env_vars.get("FIREBASE_SERVICE_ACCOUNT_JSON") or env_vars.get("FIREBASE_SERVICE_ACCOUNT_SUPREMEAI_A") or ""

secrets_to_upload = {
    "DATABASE_CONFIG": json.dumps({
        "pooler_url": "",
        "supabase_url": env_vars.get("SUPABASE_URL", "https://xtvkltzmberxekoamala.supabase.co"),
        "supabase_key": env_vars.get("SUPABASE_KEY", "")
    }),
    "AUTH_KEYS": json.dumps({
        "jwt_secret": env_vars.get("SUPREMEAI_JWT_SECRET", "")
    }),
    "LLM_PROVIDER_KEYS": json.dumps({
        "gemini": env_vars.get("GEMINI_API_KEY", ""),
        "openrouter": "",
        "openai": "",
        "groq": "",
        "deepseek": ""
    }),
    "FIREBASE_SERVICE_ACCOUNT_JSON": firebase_json,
    "ENCRYPTION_KEY": "supremeai-default-fallback-encryption-key-2026-v2"
}

for key, value in secrets_to_upload.items():
    if not value:
        print(f"Skipping {key} because value is empty")
        continue
    try:
        # Try to create first
        client.createSecret(options=CreateSecretOptions(
            environment="prod",
            project_id=project_id,
            secret_name=key,
            secret_value=value,
            path="/"
        ))
        print(f"Created {key} in prod")
    except Exception as e:
        if 'already exists' in str(e).lower() or '400' in str(e):
            try:
                # If exists, update it
                client.updateSecret(options=UpdateSecretOptions(
                    environment="prod",
                    project_id=project_id,
                    secret_name=key,
                    secret_value=value,
                    path="/"
                ))
                print(f"Updated {key} in prod")
            except Exception as e2:
                print(f"Failed to update {key}: {e2}")
        else:
            print(f"Failed to create {key}: {e}")

