import os
from datetime import datetime
from pathlib import Path
import json
from loguru import logger

def load_env_manually():
    # Load from system environment first (e.g. GitHub Actions secrets)
    env_vars = dict(os.environ)

    # Try loading from local .env
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k not in env_vars:
                env_vars[k] = v
    return env_vars

def generate_markdown():
    root = Path(".")
    output_file = Path("docs/codebase_dump.md")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    exclude_dirs = {
        ".git", "node_modules", ".venv", "dist", "build",
        "__pycache__", ".next", ".turbo", ".idea", ".vscode",
        "artifacts", "brain", ".agents"
    }

    allowed_extensions = {
        ".py", ".ts", ".tsx", ".css", ".html", ".js", ".jsx", ".json", ".sh", ".ps1", ".yml", ".yaml"
    }

    exclude_files = {
        "pnpm-lock.yaml", "package-lock.json", "poetry.lock", "codebase_dump.md"
    }

    markdown_lines = [
        "# 🧠 SupremeAI 2.0 Codebase Analysis\n",
        "# বাংলা মন্তব্য: এটি একটি স্বয়ংক্রিয়ভাবে জেনারেট করা কোডবেস ডাম্প ফাইল যা প্রজেক্টের সামগ্রিক বিশ্লেষণের জন্য ব্যবহৃত হয়।\n\n"
    ]
    markdown_lines.append(f"Generated at: {datetime.utcnow().isoformat()} UTC\n\n")

    for path in sorted(root.rglob("*")):
        if path.is_file():
            parts = path.parts
            if any(exclude in parts for exclude in exclude_dirs):
                continue
            if path.name in exclude_files:
                continue
            if path.suffix not in allowed_extensions:
                continue

            try:
                content = path.read_text(encoding="utf-8")
                rel_path = path.as_posix()
                markdown_lines.append(f"## File: `{rel_path}`\n")

                lang = path.suffix.lstrip(".")
                if lang in ("tsx", "ts", "jsx", "js"):
                    lang = "typescript" if lang.startswith("t") else "javascript"
                elif lang in ("yml", "yaml"):
                    lang = "yaml"
                elif lang == "py":
                    lang = "python"
                elif lang == "sh":
                    lang = "bash"
                elif lang == "ps1":
                    lang = "powershell"

                markdown_lines.append(f"```{lang}\n{content}\n```\n\n")
            except Exception as e:
                logger.debug(f"Skipping malformed or blocked file processing stage: {e}")

    output_content = "".join(markdown_lines)
    output_file.write_text(output_content, encoding="utf-8")
    print(f"Generated codebase markdown locally at {output_file}")
    return output_file

def send_to_telegram(file_path: Path, env: dict):
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("ADMIN_TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram configuration missing. Skipping Telegram send.")
        return

    print("Sending codebase dump to Telegram...")
    url = f"https://api.telegram.org/bot{token}/sendDocument"

    # Using urllib/http.client to avoid external requests/dependencies (like requests) in lightweight runners
    import urllib.request
    import urllib.parse

    try:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        data = []
        data.append(f"--{boundary}".encode('utf-8'))
        data.append('Content-Disposition: form-data; name="chat_id"'.encode('utf-8'))
        data.append(''.encode('utf-8'))
        data.append(str(chat_id).encode('utf-8'))

        data.append(f"--{boundary}".encode('utf-8'))
        filename = f"codebase_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        data.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode('utf-8'))
        data.append('Content-Type: text/markdown'.encode('utf-8'))
        data.append(''.encode('utf-8'))
        data.append(file_path.read_bytes())
        data.append(f"--{boundary}--".encode('utf-8'))

        body = b"\r\n".join(data)
        req = urllib.request.Request(url, data=body)
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

        with urllib.request.urlopen(req) as res:
            res.read().decode('utf-8')
            print("Telegram document sent successfully!")
    except Exception as e:
        print(f"Failed to send to Telegram: {e}")

def sync_to_supabase(file_path: Path, env: dict):
    supabase_url = env.get("SUPABASE_URL")
    # Prefer Service Role key for administrative operations like write/delete
    supabase_key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_KEY")
    bucket_name = "codebase-dumps"

    if not supabase_url or not supabase_key:
        print("Supabase configuration missing. Skipping Supabase sync.")
        return

    print("Uploading codebase dump to Supabase Storage...")
    import urllib.request
    import urllib.parse

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"codebase_dump_{timestamp}.md"
    upload_url = f"{supabase_url}/storage/v1/object/{bucket_name}/{filename}"

    try:
        # Create bucket if it doesn't exist (fails silently if exists)
        create_bucket_url = f"{supabase_url}/storage/v1/bucket"
        bucket_req = urllib.request.Request(
            create_bucket_url,
            data=json.dumps({"id": bucket_name, "name": bucket_name, "public": False}).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {supabase_key}",
                "apikey": supabase_key,
                "API-Key": supabase_key,
                "Content-Type": "application/json"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(bucket_req) as br:
                br.read()
        except Exception as e:
            logger.debug(f"Google Cloud Storage bucket operation failed or conflicted: {e}")

        # Upload File
        upload_req = urllib.request.Request(
            upload_url,
            data=file_path.read_bytes(),
            headers={
                "Authorization": f"Bearer {supabase_key}",
                "apikey": supabase_key,
                "API-Key": supabase_key,
                "Content-Type": "text/markdown"
            },
            method="POST"
        )
        with urllib.request.urlopen(upload_req) as ur:
            ur.read()
            print(f"Successfully uploaded {filename} to Supabase Storage!")

        # Enforce last 5 retention policy
        list_url = f"{supabase_url}/storage/v1/object/list/{bucket_name}"
        list_req = urllib.request.Request(
            list_url,
            data=json.dumps({"limit": 100, "sortBy": {"column": "name", "order": "asc"}}).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {supabase_key}",
                "apikey": supabase_key,
                "API-Key": supabase_key,
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(list_req) as lr:
            files = json.loads(lr.read().decode('utf-8'))

        # Filter files starting with codebase_dump_
        dump_files = [f for f in files if f.get("name", "").startswith("codebase_dump_")]

        if len(dump_files) > 5:
            files_to_delete = dump_files[:-5]
            print(f"Found {len(dump_files)} files. Deleting oldest {len(files_to_delete)} files...")

            delete_url = f"{supabase_url}/storage/v1/object/{bucket_name}"
            delete_req = urllib.request.Request(
                delete_url,
                data=json.dumps({"prefixes": [f["name"] for f in files_to_delete]}).encode('utf-8'),
                headers={
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json"
                },
                method="DELETE"
            )
            with urllib.request.urlopen(delete_req) as dr:
                dr.read()
                print("Old codebase dumps deleted successfully!")

    except Exception as e:
        print(f"Failed to sync with Supabase: {e}")

if __name__ == "__main__":
    env = load_env_manually()
    file_path = generate_markdown()
    send_to_telegram(file_path, env)
    sync_to_supabase(file_path, env)
