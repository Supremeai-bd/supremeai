import os
import re
import sys
import requests

# বাংলা: কোডবেসে TODO, FIXME এবং HACK কমেন্ট স্ক্যান করে গিটহাব ইস্যু তৈরি করার অটোমেশন স্ক্রিপ্ট
SCAN_DIRS = ["backend", "apps", "scripts"]
IGNORE_PATTERNS = [r"\.venv", r"node_modules", r"\.git", r"__pycache__"]

TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK)\s*:\s*(.*)", re.IGNORECASE)

def scan_todos():
    todos = []
    for scan_dir in SCAN_DIRS:
        if not os.path.exists(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir):
            # ignore patterns
            dirs[:] = [d for d in dirs if not any(re.search(pat, d) for pat in IGNORE_PATTERNS)]
            for file in files:
                if not file.endswith((".py", ".ts", ".js", ".tsx", ".jsx", ".yml", ".yaml")):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, 1):
                            match = TODO_PATTERN.search(line)
                            if match:
                                tag = match.group(1).upper()
                                message = match.group(2).strip()
                                todos.append({
                                    "file": file_path,
                                    "line": i,
                                    "tag": tag,
                                    "message": message
                                })
                except Exception as e:
                    print(f"Warning: Unable to read file {file_path}: {e}")
    return todos

def create_github_issues(todos):
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        print("⚠️ GITHUB_TOKEN or GITHUB_REPOSITORY is not set. Skipping GitHub Issue creation.")
        return

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # fetch existing tech-debt issues to avoid duplicates
    existing_titles = set()
    url = f"https://api.github.com/repos/{repo}/issues"
    params = {"labels": "tech-debt", "state": "open", "per_page": 100}
    try:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 200:
            existing_titles = {issue["title"] for issue in r.json()}
    except Exception as e:
        print(f"Error fetching issues: {e}")

    for todo in todos[:10]: # limit to 10 issues per run to avoid spamming
        title = f"[{todo['tag']}] {todo['message']} ({os.path.basename(todo['file'])})"
        if title in existing_titles:
            print(f"🔄 Issue already exists: {title}")
            continue

        body = (
            f"**File:** [{todo['file']}](file://{os.path.abspath(todo['file'])}#L{todo['line']})\n"
            f"**Line Number:** {todo['line']}\n"
            f"**Tag:** `{todo['tag']}`\n\n"
            f"Please address this technical debt in the codebase."
        )
        data = {
            "title": title,
            "body": body,
            "labels": ["tech-debt", "automated"]
        }
        try:
            res = requests.post(url, headers=headers, json=data)
            if res.status_code == 201:
                print(f"✅ Created issue: {title}")
            else:
                print(f"❌ Failed to create issue: {title}. Status: {res.status_code}")
        except Exception as e:
            print(f"Error creating issue: {e}")

if __name__ == "__main__":
    print("🔍 Scanning for TODO, FIXME, and HACK tags in the codebase...")
    all_todos = scan_todos()
    print(f"📝 Found {len(all_todos)} tags.")
    for t in all_todos:
        print(f"- {t['tag']} at {t['file']}:{t['line']}: {t['message']}")

    if len(sys.argv) > 1 and sys.argv[1] == "--create-issues":
        create_github_issues(all_todos)
