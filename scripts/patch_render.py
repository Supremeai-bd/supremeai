import urllib.request
import json
import os

api_key = os.environ.get("RENDER_API_KEY", "")
# বাংলা মন্তব্য: প্রাইমারি অ্যাকাউন্টের সঠিক সার্ভিস আইডি সেট করা হলো
service_id = "srv-d9d3n58js32c738n79k0"

url = f"https://api.render.com/v1/services/{service_id}"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        service = json.loads(response.read().decode())
        print("Current service:", service)
except Exception as e:
    print(e.read().decode())
