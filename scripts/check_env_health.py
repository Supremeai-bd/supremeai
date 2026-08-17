import urllib.request
import urllib.error
import json
import ssl

def check_url(url, name, is_json_status=False, json_key_path=None):
    context = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=context, timeout=10) as response:
            status_code = response.getcode()
            if status_code == 200:
                if is_json_status and json_key_path:
                    data = json.loads(response.read().decode())
                    # simplified nested key extraction
                    val = data
                    for key in json_key_path:
                        val = val.get(key, {})
                    if val == 'none' or val == 'operational' or val == 'All Systems Operational':
                        print(f"[OK] {name}: Operational ({url})")
                    else:
                        print(f"[WARN] {name}: Degraded or Issues Detected - {val} ({url})")
                else:
                    print(f"[OK] {name}: OK ({url})")
            else:
                print(f"[FAIL] {name}: Failed with status {status_code} ({url})")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"[OK] {name}: Online (Auth Required) ({url})")
        else:
            print(f"[FAIL] {name}: HTTP Error {e.code} ({url})")
    except urllib.error.URLError as e:
        print(f"[FAIL] {name}: URL Error {e.reason} ({url})")
    except Exception as e:
        print(f"[FAIL] {name}: Error {e} ({url})")

def main():
    print("======================================")
    print(" SupremeAI Environment Health Check")
    print("======================================\n")

    # Internal Environments
    print("--- Internal Services ---")
    check_url("https://supremeai-frontend-6nwi.onrender.com/", "Frontend (Render)")
    check_url("https://supremeai-admin.web.app/", "Admin Panel (Firebase)")
    # Assuming backend onrender health endpoint
    check_url("https://supremeai-backend-docker.onrender.com/health/aggregated", "Backend (Render)")
    print("")

    # External Dependencies
    print("--- External Dependencies ---")
    check_url("https://status.render.com/api/v2/status.json", "Render Platform", True, ["status", "indicator"])
    check_url("https://status.supabase.com/api/v2/status.json", "Supabase Platform", True, ["status", "indicator"])
    check_url("https://status.infisical.com/api/v2/status.json", "Infisical Platform", True, ["status", "indicator"])
    check_url("https://www.cloudflarestatus.com/api/v2/status.json", "Cloudflare", True, ["status", "indicator"])
    check_url("https://status.upstash.com/api/v2/status.json", "Upstash (Redis)", True, ["status", "indicator"])
    check_url("https://www.githubstatus.com/api/v2/status.json", "GitHub", True, ["status", "indicator"])

    print("\n--- AI LLM Providers ---")
    check_url("https://status.openai.com/api/v2/status.json", "OpenAI", True, ["status", "indicator"])
    check_url("https://status.anthropic.com/api/v2/status.json", "Anthropic", True, ["status", "indicator"])
    # Some providers don't have standard Atlassian APIs but we try standard ping for them
    check_url("https://api.groq.com/openai/v1/models", "Groq API")
    check_url("https://openrouter.ai/api/v1/models", "OpenRouter API")
    
    print("\n======================================")
    print("Health check completed.")
    print("======================================")

if __name__ == "__main__":
    main()
