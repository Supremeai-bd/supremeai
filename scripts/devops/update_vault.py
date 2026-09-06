from infisical_client import (
    AuthenticationOptions,
    ClientSettings,
    InfisicalClient,
    UniversalAuthMethod,
    UpdateSecretOptions,
)

import os

client_id = os.getenv("INFISICAL_CLIENT_ID", "")
client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "")
project_id = os.getenv("INFISICAL_PROJECT_ID", "")

if not client_id or not project_id:
    raise RuntimeError("INFISICAL_CLIENT_ID and INFISICAL_PROJECT_ID must be provided via environment variables.")

render_svc_id = os.getenv("RENDER_PRIMARY_SVC_ID", "")
if not render_svc_id:
    raise RuntimeError("RENDER_PRIMARY_SVC_ID must be provided via environment variables.")

client = InfisicalClient(
    ClientSettings(
        auth=AuthenticationOptions(
            universal_auth=UniversalAuthMethod(
                client_id=client_id,
                client_secret=client_secret
            )
        )
    )
)

try:
    client.updateSecret(
        options=UpdateSecretOptions(
            secret_name="RENDER_PRIMARY_SVC_ID",
            secret_value=render_svc_id,
            environment="prod",
            project_id=project_id,
            path="/"
        )
    )
    print("SUCCESS: Updated RENDER_PRIMARY_SVC_ID in prod")
except Exception as e:
    print(f"ERROR: {e}")
