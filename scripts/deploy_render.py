# বাংলা মন্তব্য: .env থেকে Render API Key রিড করা এবং সঠিক সার্ভিস আইডিতে ডিপ্লয় ট্র্রিগার করা
import os
import urllib.request
import re

api_key = os.environ.get("RENDER_API_KEY", "")
api_key_backup = os.environ.get("RENDER_API_KEY_BACKUP", "")

if not api_key or not api_key_backup:
    if os.path.exists(".env"):
        env_text = open(".env", encoding="utf-8").read()
        m1 = re.search(r'RENDER_API_KEY="([^"]+)"', env_text)
        m2 = re.search(r'RENDER_API_KEY_BACKUP="([^"]+)"', env_text)
        if m1 and not api_key:
            api_key = m1.group(1)
        if m2 and not api_key_backup:
            api_key_backup = m2.group(1)

# প্রতিটি সার্ভিস আইডিকে তার নিজ নিজ অ্যাকাউন্টের API Key-র সাথে ম্যাপ করা হচ্ছে
# বাংলা মন্তব্য: User Backend ও Admin Backend-এর সঠিক সার্ভিস আইডি
service_mappings = [
    {"name": "User Backend", "sid": "srv-d9d3n58js32c738n79k0", "key": api_key},
    {"name": "Admin Backend", "sid": "srv-da35gg2bkg8c73fp1mu0", "key": api_key_backup}
]

for service in service_mappings:
    sid = service["sid"]
    key = service["key"]
    if not key:
        print(f"Skipping deploy for {sid}: API key not set")
        continue

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    req = urllib.request.Request(f"https://api.render.com/v1/services/{sid}/deploys", data=b'{}', headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Triggered deploy for {sid}: {response.status}")
    except Exception as e:
        print(f"Failed deploy for {sid}: {e}")
