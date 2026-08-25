import urllib.request, json, os

client_id = "9f2363cf-3cec-43f6-b155-a8625de19250"
client_secret = "***REMOVED***"
workspace_id = "92aa20c4-aef5-4e33-82bd-efb06058aaf0"

def get_token():
    req = urllib.request.Request(
        "https://app.infisical.com/api/v1/auth/universal-auth/login",
        data=json.dumps({"clientId": client_id, "clientSecret": client_secret}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["accessToken"]

def upsert_secret(token, key, value):
    update_data = {
        "workspaceId": workspace_id,
        "environment": "prod",
        "secretPath": "/",
        "secretValue": value,
        "type": "shared"
    }
    
    req = urllib.request.Request(
        f"https://app.infisical.com/api/v3/secrets/raw/{key}",
        data=json.dumps(update_data).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PATCH"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Updated {key}")
            return
    except Exception as e:
        create_data = {
            "workspaceId": workspace_id,
            "environment": "prod",
            "secretPath": "/",
            "secretName": key,
            "secretValue": value,
            "type": "shared"
        }
        req = urllib.request.Request(
            f"https://app.infisical.com/api/v3/secrets/raw/{key}",
            data=json.dumps(create_data).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                print(f"Created {key}")
        except Exception as e2:
            print(f"Failed to create {key}: {e2}")

if __name__ == "__main__":
    token = get_token()
    secrets_to_add = {
        "ADMIN_EMAILS": '["niloyjoy7@gmail.com", "admin@supremeai.com"]'
    }
    
    for k, v in secrets_to_add.items():
        upsert_secret(token, k, v)
        
    print("Done adding secrets to Infisical!")
