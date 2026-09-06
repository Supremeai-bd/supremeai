import json

from dotenv import dotenv_values
from infisical_client import (
    AuthenticationOptions,
    ClientSettings,
    CreateSecretOptions,
    InfisicalClient,
    UniversalAuthMethod,
    UpdateSecretOptions,
)

import os

client_id = os.getenv("INFISICAL_CLIENT_ID", "9f2363cf-3cec-43f6-b155-a8625de19250")
client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "")
project_id = os.getenv("INFISICAL_PROJECT_ID", "92aa20c4-aef5-4e33-82bd-efb06058aaf0")

env_vars = dotenv_values('.env')
client_secret = client_secret or env_vars.get("INFISICAL_CLIENT_SECRET", "")
client_id = os.getenv("INFISICAL_CLIENT_ID") or env_vars.get("INFISICAL_CLIENT_ID", client_id)
project_id = os.getenv("INFISICAL_PROJECT_ID") or env_vars.get("INFISICAL_PROJECT_ID", project_id)

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
        "supabase_url": env_vars.get("SUPABASE_URL", ""),
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
    "ENCRYPTION_KEY": env_vars.get("ENCRYPTION_KEY", os.getenv("ENCRYPTION_KEY", ""))
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

