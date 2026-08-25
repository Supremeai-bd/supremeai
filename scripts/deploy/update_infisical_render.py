from infisical_client import ClientSettings, InfisicalClient, AuthenticationOptions, UniversalAuthMethod, CreateSecretOptions, UpdateSecretOptions

client_id = '9f2363cf-3cec-43f6-b155-a8625de19250'
client_secret = '***REMOVED***'
project_id = '92aa20c4-aef5-4e33-82bd-efb06058aaf0'

client = InfisicalClient(ClientSettings(
    auth=AuthenticationOptions(
        universal_auth=UniversalAuthMethod(
            client_id=client_id,
            client_secret=client_secret
        )
    )
))

key = 'RENDER_PRIMARY_SVC_ID'
value = 'srv-da666f8u01pc739bm3t0'

try:
    client.createSecret(options=CreateSecretOptions(
        environment="prod",
        project_id=project_id,
        secret_name=key,
        secret_value=value,
        path="/"
    ))
    print(f"Created {key} in prod")
except Exception as e:
    try:
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
