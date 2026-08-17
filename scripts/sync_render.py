import json
import os
import requests
from dotenv import dotenv_values

render_api_key = os.environ.get("RENDER_API_KEY")
if not render_api_key:
    raise ValueError("RENDER_API_KEY environment variable is missing!")
service_id = "srv-d9d3n58js32c738n79k0"
url = f"https://api.render.com/v1/services/{service_id}/env-vars"

# Read existing render vars
headers = {
    "Authorization": f"Bearer {render_api_key}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)
if response.status_code != 200:
    print("Failed to get render vars:", response.text)
    exit(1)

existing_vars = response.json()
env_dict = {item['envVar']['key']: item['envVar']['value'] for item in existing_vars}

# Read local infisical_upload.env
local_vars = dotenv_values("infisical_upload.env")

# Merge
for k, v in local_vars.items():
    if v is not None:
        env_dict[k] = v

# Read INFISICAL_TOKEN from .env directly since it might not be in infisical_upload.env
root_vars = dotenv_values(".env")
for k in ["INFISICAL_TOKEN", "INFISICAL_CLIENT_SECRET", "INFISICAL_CLIENT_ID", "INFISICAL_PROJECT_ID"]:
    if k in root_vars and root_vars[k]:
        env_dict[k] = root_vars[k]

# Format for Render API PUT
payload = [{"key": k, "value": str(v)} for k, v in env_dict.items()]

put_response = requests.put(url, headers=headers, json=payload)
if put_response.status_code == 200:
    print("Successfully synced secrets to Render!")
else:
    print("Failed to sync secrets:", put_response.text)
