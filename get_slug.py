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
        
    req3 = urllib.request.Request(
        'https://app.infisical.com/api/v3/secrets/raw/RENDER_API_KEY?workspaceId=92aa20c4-aef5-4e33-82bd-efb06058aaf0&environment=prod&secretPath=/',
        headers={'Authorization': f'Bearer {token}'}
    )
    with urllib.request.urlopen(req3) as resp:
        data = json.loads(resp.read().decode())
        render_api_key = data['secret']['secretValue']
        
    print(f"Got RENDER_API_KEY")
    
    req4 = urllib.request.Request(
        'https://api.render.com/v1/services/srv-d9d3n58js32c738n79k0',
        headers={'Authorization': f'Bearer {render_api_key}'}
    )
    try:
        with urllib.request.urlopen(req4) as resp:
            data = json.loads(resp.read().decode())
            print(f"Service info: {data['service']['name']}")
    except Exception as e:
        print(f"Render API Error: {e}")
except Exception as e:
    print('Error:', e)
