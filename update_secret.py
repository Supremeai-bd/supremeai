import urllib.request, json

try:
    req1 = urllib.request.Request(
        'https://app.infisical.com/api/v1/auth/universal-auth/login',
        data=json.dumps({
            "clientId": "9f2363cf-3cec-43f6-b155-a8625de19250",
            "clientSecret": "***REMOVED***"
        }).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req1) as resp:
        token = json.loads(resp.read().decode())['accessToken']
        
    update_data = {
        "workspaceId": "92aa20c4-aef5-4e33-82bd-efb06058aaf0",
        "environment": "prod",
        "secretPath": "/",
        "secretValue": "srv-da5i4frm8hqs73cpp5hg",
        "type": "shared"
    }
    
    req_update = urllib.request.Request(
        'https://app.infisical.com/api/v3/secrets/raw/RENDER_PRIMARY_SVC_ID',
        data=json.dumps(update_data).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='PATCH'
    )
    with urllib.request.urlopen(req_update) as resp:
        data = json.loads(resp.read().decode())
        print(f"Secret updated successfully: {data['secret']['secretKey']} = {data['secret']['secretValue']}")
except Exception as e:
    print('Error:', e)
