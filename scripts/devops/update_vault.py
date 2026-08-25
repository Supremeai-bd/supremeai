from infisical_client import (
    AuthenticationOptions,
    ClientSettings,
    InfisicalClient,
    UniversalAuthMethod,
    UpdateSecretOptions,
)

client_id = "9f2363cf-3cec-43f6-b155-a8625de19250"
client_secret = "***REMOVED***"
project_id = "92aa20c4-aef5-4e33-82bd-efb06058aaf0"

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
            secret_value="srv-da666f8u01pc739bm3t0",
            environment="prod",
            project_id=project_id,
            path="/"
        )
    )
    print("SUCCESS: Updated RENDER_PRIMARY_SVC_ID in prod")
except Exception as e:
    print(f"ERROR: {e}")
