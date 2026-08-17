import os
import sys
import urllib.request
import urllib.error
import json
import time

def trigger_deploy_for_service(api_key: str, service_id: str, image_url: str = None) -> bool:
    url = f"https://api.render.com/v1/services/{service_id}/deploys"
    payload = {"clearCache": "do_not_clear"}
    if image_url:
        payload["imageUrl"] = image_url

    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload).encode("utf-8")
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            if status_code in (200, 201, 202):
                res = json.loads(body) if body else {}
                deploy_id = res.get("id", "accepted")
                print(f"✅ Render Deploy triggered successfully for {service_id} (Deploy ID: {deploy_id}) [HTTP {status_code}]")
                return True
            else:
                print(f"⚠️ Unexpected status code {status_code} for {service_id}: {body}")
                return False
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"❌ Render API HTTP Error ({e.code}) for {service_id}: {err_body}")
        return False
    except Exception as e:
        print(f"❌ Render API Connection/Network Error for {service_id}: {e}")
        return False

def trigger_via_api(api_key: str, default_svc_id: str, image_url: str = None) -> bool:
    if not api_key:
        return False

    # Try explicit service ID first if available
    if default_svc_id:
        print(f"🚀 Attempting direct deploy trigger on service: {default_svc_id}")
        if trigger_deploy_for_service(api_key, default_svc_id, image_url):
            return True

    # Otherwise list services and search for backend
    print("🔍 Fetching service list from Render API...")
    url = "https://api.render.com/v1/services?limit=100"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            services = json.loads(response.read().decode("utf-8"))
            for item in services:
                svc = item.get("service", item)
                name = svc.get("name", "")
                svc_id = svc.get("id", "")
                if "supremeai" in name.lower() and "backend" in name.lower():
                    print(f"🎯 Discovered backend service: {name} ({svc_id})")
                    if trigger_deploy_for_service(api_key, svc_id, image_url):
                        return True
    except Exception as e:
        print(f"⚠️ Could not list Render services: {e}")
    return False

def trigger_via_webhook(webhook_url: str) -> bool:
    if not webhook_url:
        return False
    print("🪝 Attempting deploy trigger via Render Deploy Webhook...")
    req = urllib.request.Request(webhook_url, method="POST", headers={
        "User-Agent": "SupremeAI-CI"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"✅ Webhook trigger accepted with HTTP {resp.getcode()}")
            return True
    except Exception as e:
        print(f"❌ Deploy Webhook failed: {e}")
        return False

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    primary_key = os.environ.get("RENDER_API_KEY", "").strip()
    primary_svc = os.environ.get("PRIMARY_SVC_ID", "").strip() or "srv-da07ogmgekts739amqa0"
    deploy_hook = os.environ.get("RENDER_DEPLOY_HOOK_URL", "").strip()
    image_url = os.environ.get("IMAGE_URL", "").strip() or None

    if not primary_key and not deploy_hook:
        print("⚠️ No Render credentials found (RENDER_API_KEY / RENDER_DEPLOY_HOOK_URL). Skipping deploy.")
        sys.exit(1)

    print("🚀 Triggering Render Deployment...")
    # 1. Try Primary API Key first
    if primary_key:
        print(f"🔑 Trying Primary Render API Key (Service: {primary_svc})...")
        if trigger_via_api(primary_key, primary_svc, image_url):
            print("🎉 Primary deployment initiated successfully!")
            sys.exit(0)
        else:
            print("⚠️ Primary deployment failed or key quota exhausted. Falling back to Webhook...")

    # 2. Fallback to Deploy Hook
    if deploy_hook:
        print(f"🔗 Triggering via Deploy Hook Webhook ({deploy_hook})...")
        if trigger_via_webhook(deploy_hook):
            print("🎉 Deployment initiated successfully via webhook!")
            sys.exit(0)
        else:
            print("❌ Webhook trigger failed.")

    print("❌ All deployment triggers failed.")
    sys.exit(1)

if __name__ == "__main__":
    main()
