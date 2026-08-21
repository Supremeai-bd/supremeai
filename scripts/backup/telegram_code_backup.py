#!/usr/bin/env python3
# ruff: noqa: BLE001, S110, ASYNC230, SIM102
"""
SupremeAI 2.0 — Automated Telegram Codebase Backup Runner (Zip & Markdown Digest)
---------------------------------------------------------------------------------
Generates an AI-optimized clean zip and unified single-file Markdown digest (.md) 
of the project and uploads them directly to Telegram Cloud Vault on Push.

Usage:
    python scripts/backup/telegram_code_backup.py --format all
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=True)

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff",
    ".jsonl", ".parquet", ".arrow", ".h5", ".sqlite", ".db", ".csv",
    ".zip", ".tar", ".gz", ".7z", ".exe", ".dll", ".so", ".dylib", ".wasm", ".map", ".tmp"
}

IGNORED_DIRECTORY_PREFIXES = (
    "_archive/",
    "reports/",
    "backend/docs/autogen/",
    "backend/reports/",
)

def is_knowledge_base_doc(rel_path_posix: str) -> bool:
    return rel_path_posix.startswith("docs/knowledge-base/") and rel_path_posix.endswith(".md")

def is_excluded_for_ai(rel_path_posix: str) -> bool:
    ext = Path(rel_path_posix).suffix.lower()
    filename = Path(rel_path_posix).name.lower()

    if ext in IGNORED_EXTENSIONS:
        return True

    for prefix in IGNORED_DIRECTORY_PREFIXES:
        if rel_path_posix.startswith(prefix) or rel_path_posix == prefix.rstrip("/"):
            return True

    if "failure_logs" in filename or "failed_job_log" in filename or filename.endswith(".log"):
        return True

    if rel_path_posix == "docs" or rel_path_posix.startswith("docs/"):
        if not is_knowledge_base_doc(rel_path_posix):
            return True

    return bool(rel_path_posix == ".git" or rel_path_posix.startswith(".git/"))

def get_git_filtered_files(project_dir: Path) -> list[Path]:
    try:
        cmd = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
        result = subprocess.run(
            cmd,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True
        )
        file_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        files = [project_dir / rel_path for rel_path in file_lines]
        
        env_example = project_dir / ".env.example"
        if env_example.exists() and env_example not in files:
            files.append(env_example)
            
        return files
    except Exception as e:
        print(f"[!] Warning: Git command failed ({e}). Scanning manually...")
        return fallback_file_scanner(project_dir)

def fallback_file_scanner(project_dir: Path) -> list[Path]:
    ignored = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
        ".pytest_cache", ".ruff_cache", ".mypy_cache", ".coverage", "*.pyc", "*.pyo",
        ".next", ".nuxt", "coverage", ".turbo", "_archive"
    }
    selected = []
    for root, dirs, files in os.walk(project_dir):
        root_p = Path(root)
        try:
            root_p.relative_to(project_dir)
        except ValueError:
            continue
        dirs[:] = [d for d in dirs if d not in ignored and d != ".git"]
        for f in files:
            selected.append(root_p / f)
    return selected

EXT_TO_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".md": "markdown",
    ".toml": "toml",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
    ".bash": "bash",
    ".ps1": "powershell",
    ".dockerfile": "dockerfile",
    ".env.example": "ini",
    ".txt": "text",
    ".xml": "xml",
}

def create_ai_zip(project_dir: Path, output_zip_path: Path) -> tuple[int, int, int]:
    all_files = get_git_filtered_files(project_dir)
    filtered_files: list[tuple[Path, str]] = []

    for file_path in all_files:
        if not file_path.exists() or file_path.is_dir():
            continue
        try:
            rel_path = file_path.relative_to(project_dir).as_posix()
        except ValueError:
            continue

        if not is_excluded_for_ai(rel_path):
            filtered_files.append((file_path, rel_path))

    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    total_uncompressed = 0

    with zipfile.ZipFile(output_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path, rel_path in filtered_files:
            try:
                sz = file_path.stat().st_size
                total_uncompressed += sz
                zf.write(file_path, arcname=rel_path)
            except Exception as e:
                print(f"[!] Skip {rel_path}: {e}")

    final_size = output_zip_path.stat().st_size
    return len(filtered_files), total_uncompressed, final_size

def create_ai_markdown_digest(project_dir: Path, output_md_path: Path, git_info: dict[str, str]) -> tuple[int, int]:
    all_files = get_git_filtered_files(project_dir)
    filtered_files: list[tuple[Path, str]] = []

    for file_path in all_files:
        if not file_path.exists() or file_path.is_dir():
            continue
        try:
            rel_path = file_path.relative_to(project_dir).as_posix()
        except ValueError:
            continue

        if not is_excluded_for_ai(rel_path):
            filtered_files.append((file_path, rel_path))

    # Sort files alphabetically
    filtered_files.sort(key=lambda x: x[1])

    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md_lines: list[str] = [
        "# 🔱 SupremeAI 2.0 Codebase Snapshot Digest\n",
        f"- **Branch:** `{git_info['branch']}`",
        f"- **Commit:** `{git_info['commit']}`",
        f"- **Message:** {git_info['message']}",
        f"- **Author:** {git_info['author']}",
        f"- **Timestamp:** `{timestamp_str}`",
        f"- **Total Active Files:** {len(filtered_files):,}\n",
        "## 📑 Table of Contents\n",
    ]

    for _, rel_path in filtered_files:
        md_lines.append(f"- [`{rel_path}`](#{rel_path.replace('/', '-').replace('.', '-')})")

    md_lines.append("\n---\n\n## 📂 Codebase File Contents\n")

    for file_path, rel_path in filtered_files:
        ext = file_path.suffix.lower()
        lang = EXT_TO_LANG.get(ext, "text")
        if file_path.name.lower() == "dockerfile":
            lang = "dockerfile"
        elif file_path.name.lower() == ".env.example":
            lang = "ini"

        try:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = file_path.read_text(encoding="latin-1", errors="replace")

            # Avoid triple-backtick collision by using 4 backticks if needed
            fence = "````" if "```" in content else "```"
            anchor = rel_path.replace('/', '-').replace('.', '-')
            md_lines.append(f"<a id=\"{anchor}\"></a>\n### 📄 `{rel_path}`\n")
            md_lines.append(f"{fence}{lang}\n{content}\n{fence}\n")
        except Exception as e:
            md_lines.append(f"### 📄 `{rel_path}`\n*(Error reading file: {e})*\n")

    full_md_text = "\n".join(md_lines)
    output_md_path.write_text(full_md_text, encoding="utf-8", errors="replace")
    final_size = output_md_path.stat().st_size

    return len(filtered_files), final_size

def get_git_commit_info(project_dir: Path) -> dict[str, str]:
    info = {"commit": "N/A", "message": "Automated Backup", "author": "CI/CD Agent", "branch": "main"}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=project_dir, text=True).strip()
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir, text=True).strip()
        msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], cwd=project_dir, text=True).strip()
        author = subprocess.check_output(["git", "log", "-1", "--pretty=%an"], cwd=project_dir, text=True).strip()
        info.update({"commit": commit, "branch": branch, "message": msg.splitlines()[0] if msg else "N/A", "author": author})
    except Exception:
        pass
    return info

async def upload_document_to_telegram(
    doc_path: Path,
    caption: str,
    mime_type: str,
    bot_token: str,
    chat_id: str,
) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    size_mb = doc_path.stat().st_size / (1024 * 1024)

    print(f"📤 Uploading {doc_path.name} ({size_mb:.2f} MB) to Telegram Chat {chat_id}...")
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            with open(doc_path, "rb") as f:
                files = {"document": (doc_path.name, f, mime_type)}
                data = {"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"}
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                res = response.json()
                if res.get("ok"):
                    print(f"✅ Upload Successful for {doc_path.name}!")
                    return True
                else:
                    print(f"❌ Telegram API Error for {doc_path.name}: {res}")
                    return False
    except Exception as e:
        print(f"❌ Telegram Upload Exception for {doc_path.name}: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description="SupremeAI Telegram Codebase Backup (Zip & Markdown Digest)")
    parser.add_argument("--dry-run", action="store_true", help="Create archives without uploading to Telegram")
    parser.add_argument("--out-dir", type=str, default="", help="Custom output directory")
    parser.add_argument("--format", choices=["all", "zip", "md"], default="all", help="Backup format: zip, md, or all")
    args = parser.parse_args()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not args.dry_run and (not bot_token or not chat_id):
        print("⚠️ Warning: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
        print("   Proceeding in dry-run mode (local generation only)...")
        args.dry_run = True

    git_info = get_git_commit_info(ROOT_DIR)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    out_dir = Path(args.out_dir) if args.out_dir else ROOT_DIR / "temp_backup"

    success_all = True

    # ── 1. Create & Upload ZIP Archive ──────────────────────────
    if args.format in ("all", "zip"):
        zip_filename = f"supremeai_{git_info['branch']}_{git_info['commit']}_{timestamp}.zip"
        zip_path = out_dir / zip_filename
        print("🚀 Generating AI-Ready Zip Archive...")
        start_time = time.time()
        file_count, uncompressed_size, compressed_size = create_ai_zip(ROOT_DIR, zip_path)
        elapsed = time.time() - start_time
        cmp_mb = compressed_size / (1024 * 1024)
        unc_mb = uncompressed_size / (1024 * 1024)
        ratio = (1 - (compressed_size / uncompressed_size)) * 100 if uncompressed_size > 0 else 0
        print(f"✨ Zip Created in {elapsed:.2f}s: {zip_path} ({cmp_mb:.2f} MB, {file_count} files)")

        if not args.dry_run:
            zip_caption = (
                f"📦 <b>SupremeAI Codebase Vault Backup (.zip)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌿 <b>Branch:</b> <code>{git_info['branch']}</code>\n"
                f"🔖 <b>Commit:</b> <code>{git_info['commit']}</code>\n"
                f"💬 <b>Message:</b> <i>{git_info['message']}</i>\n"
                f"👤 <b>Author:</b> <code>{git_info['author']}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 <b>Active Files:</b> {file_count:,}\n"
                f"📊 <b>Zip Size:</b> {cmp_mb:.2f} MB (Saved {ratio:.1f}% from {unc_mb:.2f} MB)\n"
                f"🎯 <b>Format:</b> Compressed Project Archive\n"
                f"🕒 <b>Timestamp:</b> <code>{timestamp_str}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <i>Automated Zero-Cost Backup Pipeline</i>"
            )
            ok_zip = await upload_document_to_telegram(
                doc_path=zip_path,
                caption=zip_caption,
                mime_type="application/zip",
                bot_token=bot_token,
                chat_id=chat_id,
            )
            if not ok_zip:
                success_all = False

            if os.getenv("GITHUB_ACTIONS"):
                zip_path.unlink(missing_ok=True)

    # ── 2. Create & Upload Markdown Digest ───────────────────────
    if args.format in ("all", "md"):
        md_filename = f"supremeai_{git_info['branch']}_{git_info['commit']}_{timestamp}_digest.md"
        md_path = out_dir / md_filename
        print("🚀 Generating Unified Single-File Markdown Digest (.md)...")
        start_time = time.time()
        md_file_count, md_size_bytes = create_ai_markdown_digest(ROOT_DIR, md_path, git_info)
        elapsed = time.time() - start_time
        md_mb = md_size_bytes / (1024 * 1024)
        print(f"✨ Markdown Digest Created in {elapsed:.2f}s: {md_path} ({md_mb:.2f} MB, {md_file_count} files)")

        if not args.dry_run:
            md_caption = (
                f"📄 <b>SupremeAI Codebase AI Digest (.md)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌿 <b>Branch:</b> <code>{git_info['branch']}</code>\n"
                f"🔖 <b>Commit:</b> <code>{git_info['commit']}</code>\n"
                f"💬 <b>Message:</b> <i>{git_info['message']}</i>\n"
                f"👤 <b>Author:</b> <code>{git_info['author']}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 <b>Included Files:</b> {md_file_count:,}\n"
                f"📊 <b>Doc Size:</b> {md_mb:.2f} MB (Single-File LLM Context Ready)\n"
                f"💡 <b>Usage:</b> Drag & drop into ChatGPT / Claude / Gemini directly!\n"
                f"🕒 <b>Timestamp:</b> <code>{timestamp_str}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🧠 <i>Continuous Learning Matrix Snapshot</i>"
            )
            ok_md = await upload_document_to_telegram(
                doc_path=md_path,
                caption=md_caption,
                mime_type="text/markdown",
                bot_token=bot_token,
                chat_id=chat_id,
            )
            if not ok_md:
                success_all = False

            if os.getenv("GITHUB_ACTIONS"):
                md_path.unlink(missing_ok=True)

    if not success_all:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
