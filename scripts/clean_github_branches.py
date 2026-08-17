import os
import sys
import requests
from dotenv import load_dotenv

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Load .env
load_dotenv()

# We will use GITHUB_PAT_AUTO_FIX as requested or fallback to GITHUB_TOKEN
TOKEN = os.getenv("GITHUB_PAT_AUTO_FIX") or os.getenv("GITHUB_TOKEN")
REPO_OWNER = "paykaribazaronline"
REPO_NAME = "supremeai"
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

KEEP_BRANCHES = ["main", "master", "develop"]

def get_all_branches():
    branches = []
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads"

    while url:
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"Failed to fetch branches: {response.status_code} {response.text}")
            break

        data = response.json()
        if not isinstance(data, list):
            break

        for ref in data:
            branch_name = ref["ref"].replace("refs/heads/", "")
            branches.append(branch_name)

        # Pagination check
        if "next" in response.links:
            url = response.links["next"]["url"]
        else:
            url = None

    return branches

def delete_branch(branch_name):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/{branch_name}"
    import time
    for _ in range(3):
        try:
            response = requests.delete(url, headers=HEADERS)
            if response.status_code == 204:
                print(f"✅ Deleted: {branch_name}")
                time.sleep(0.5)
                return
            elif response.status_code == 404:
                print(f"✅ Already deleted: {branch_name}")
                return
            else:
                print(f"❌ Failed to delete {branch_name}: {response.status_code} {response.text}")
                time.sleep(1)
        except Exception as e:
            print(f"Connection aborted for {branch_name}, retrying... {e}")
            time.sleep(2)

if __name__ == "__main__":
    print(f"Fetching branches for {REPO_OWNER}/{REPO_NAME}...")
    branches = get_all_branches()
    print(f"Found {len(branches)} total branches.")

    deleted_count = 0
    for branch in branches:
        if branch not in KEEP_BRANCHES:
            delete_branch(branch)
            deleted_count += 1
        else:
            print(f"🛡️  Kept: {branch}")

    print(f"Cleanup complete! Deleted {deleted_count} stale branches.")
