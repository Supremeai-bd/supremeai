import urllib.request
import json
import os

# বাংলা মন্তব্য: ব্যাকআপ অ্যাকাউন্টের API Key এবং সঠিক সার্ভিস আইডি সেট করা হলো
api_key = os.environ.get("RENDER_API_KEY_BACKUP", "")
service = "srv-d9e4q5rrjlhs73bnh71g"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# বাংলা: dockerCommand শূন্য করা হলো — আগে port 10000 হার্ডকোড থাকায় render.yaml PORT=8080
# মিস্ম্যাচ হতো এবং 'No open ports detected' এরর দিত। Dockerfile CMD सার্ভার
# সঠিকভাবে $PORT নিয়ে রান করবে।
data = {
    "serviceDetails": {
        "envSpecificDetails": {
            "dockerCommand": ""
        }
    }
}
json_data = json.dumps(data).encode('utf-8')

req = urllib.request.Request(f"https://api.render.com/v1/services/{service}", data=json_data, headers=headers, method="PATCH")
try:
    with urllib.request.urlopen(req) as response:
        print(f"Updated {service}: {response.status}")
except Exception as e:
    print(f"Failed {service}: {e}")
