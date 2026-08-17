import urllib.request
import json
import os

api_key = os.environ.get("RENDER_API_KEY")
api_key_backup = os.environ.get("RENDER_API_KEY_BACKUP")

# বাংলা মন্তব্য: API Key না পাওয়া গেলে স্ক্রিপ্ট থামিয়ে দিন, অন্ধকারে অকার্যকর রিকোয়েস্ট পাঠাবেন না
if not api_key or not api_key_backup:
    raise ValueError("❌ RENDER_API_KEY বা RENDER_API_KEY_BACKUP এনভায়রনমেন্ট ভ্যারিয়েবল সেট করা হয়নি!")


# বাংলা মন্তব্য: প্রতিটি সার্ভিস আইডিকে তার নিজ নিজ অ্যাকাউন্টের API Key-র সাথে ম্যাপ করে আপডেট করা হচ্ছে
services = [
    {"sid": "srv-d9d3n58js32c738n79k0", "key": api_key},
    {"sid": "srv-d9e4q5rrjlhs73bnh71g", "key": api_key_backup}
]

# বাংলা: dockerCommand সরানো হলো — আগে port 10000 হার্ডকোড থাকায় render.yaml-এর PORT=8080
# মিস্ম্যাচ হতো এবং 'No open ports detected' এরর দিত। এখন Dockerfile-এর
# CMD ["sh", "-c", "exec python main.py"] ব্যবহার হবে, যা $PORT এনভ ভার রেসপেক্ট করে।
data = {
    "serviceDetails": {
        "envSpecificDetails": {
            "dockerCommand": ""
        }
    }
}
json_data = json.dumps(data).encode('utf-8')

for service in services:
    sid = service["sid"]
    key = service["key"]
    if not key:
        print(f"Skipping update for {sid}: API key not set")
        continue

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}", data=json_data, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Updated {sid}: {response.status}")
    except Exception as e:
        print(f"Failed {sid}: {e}")
