import os
import sys
import json
import urllib.request

# ==========================================
# ⚙️ GITHUB ENVIRONMENT VARIABLES
# ==========================================
REPO = os.getenv("GITHUB_REPOSITORY", "paykaribazaronline/supremeai")
RUN_ID = os.getenv("GITHUB_RUN_ID", "0")
ACTOR = os.getenv("GITHUB_ACTOR", "Developer")
BRANCH = os.getenv("GITHUB_REF_NAME", "main")
SHA = os.getenv("GITHUB_SHA", "unknown")[:7]
WORKFLOW_NAME = os.getenv("GITHUB_WORKFLOW", "SupremeAI CI")
JOB_STATUS = os.getenv("JOB_STATUS", "success") # Passed from the YAML

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
API_URL = os.getenv("SUPREMEAI_API_URL", "https://api.supremeai.dev")

# ==========================================
# 🎨 FORMATTING LOGIC
# ==========================================
IS_SUCCESS = (JOB_STATUS.lower() == "success")
COLOR = 3066993 if IS_SUCCESS else 15158332 # Green or Red
STATUS_ICON = "✅" if IS_SUCCESS else "❌"
TITLE = f"{STATUS_ICON} {WORKFLOW_NAME}: {JOB_STATUS.upper()}"
ACTION_URL = f"https://github.com/{REPO}/actions/runs/{RUN_ID}"

# ==========================================
# 📝 1. WRITE TO GITHUB STEP SUMMARY
# ==========================================
def write_github_summary():
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    md_content = f"""# {TITLE}
**Branch:** `{BRANCH}` | **Commit:** `{SHA}` | **Triggered By:** `@{ACTOR}`

## 🚀 Live Deployments
* **Backend API (Cloud Run):** [{API_URL}]({API_URL})

<details>
<summary>🛠️ Pipeline Details</summary>

* **Repository:** {REPO}
* **Run ID:** [{RUN_ID}]({ACTION_URL})
* **Final Status:** `{JOB_STATUS.upper()}`

</details>

[🔍 View Full Action Logs]({ACTION_URL})
"""
    with open(summary_file, "a", encoding="utf-8") as f:
        f.write(md_content)
    print("✅ GitHub Step Summary generated successfully.")

# ==========================================
# 🔔 2. SEND DISCORD RICH EMBED
# ==========================================
def send_discord_alert():
    if not DISCORD_WEBHOOK:
        print("⚠️ DISCORD_WEBHOOK_URL not set. Skipping Discord alert.")
        return

    payload = {
        "username": "SupremeAI CI/CD",
        "avatar_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
        "embeds": [
            {
                "title": TITLE,
                "url": ACTION_URL,
                "color": COLOR,
                "fields": [
                    {"name": "Branch", "value": f"`{BRANCH}`", "inline": True},
                    {"name": "Commit", "value": f"`{SHA}`", "inline": True},
                    {"name": "Developer", "value": f"@{ACTOR}", "inline": True},
                    {"name": "Live API", "value": f"[Production URL]({API_URL})", "inline": False}
                ],
                "footer": {
                    "text": f"SupremeAI Architecture v3.0 • Run ID: {RUN_ID}"
                }
            }
        ]
    }

    req = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "SupremeAI-Bot"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.getcode() in [200, 204]:
                print("✅ Discord Rich Alert sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")

# ==========================================
# 🚀 EXECUTION
# ==========================================
if __name__ == "__main__":
    print(f"Generating CI/CD Report for {REPO}...")
    write_github_summary()
    send_discord_alert()
