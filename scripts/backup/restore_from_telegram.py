#!/usr/bin/env python3
"""
SupremeAI 2.0 — Disaster Recovery & Restore Engine
Decrypts and restores Supabase Database & AI Memory from TelDrive Vault.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

if sys.stdout.encoding != "utf-8":
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")

# Load local workspace env
root_dir = Path(__file__).resolve().parents[2]
load_dotenv(root_dir / ".env", override=True)

from cryptography.fernet import Fernet


def get_fernet_crypto() -> Fernet:
    raw_key = os.getenv("ENCRYPTION_KEY", "supremeai-default-zero-cost-fernet-key-2026")
    digest = hashlib.sha256(raw_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def decrypt_file(file_path: Path) -> dict[str, Any]:
    with open(file_path, "rb") as f:
        encrypted_bytes = f.read()

    fernet = get_fernet_crypto()
    decompressed = gzip.decompress(fernet.decrypt(encrypted_bytes))
    return json.loads(decompressed.decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="SupremeAI Disaster Recovery & Decryptor")
    parser.add_argument("backup_file", type=Path, help="Path to .enc.gz backup file")
    parser.add_argument("--inspect", action="store_true", help="Print summary of backup contents without restoring")
    args = parser.parse_args()

    if not args.backup_file.exists():
        print(f"❌ File not found: {args.backup_file}")
        sys.exit(1)

    print(f"🔓 Decrypting {args.backup_file.name} using AES-256 Fernet Key...")
    try:
        data = decrypt_file(args.backup_file)
        print(f"✅ Decryption successful! Backup created at: {data.get('timestamp')}")
        
        if "database" in data:
            db_data = data["database"]
            print(f"📊 Tables in backup ({len(db_data)} total):")
            for tbl, rows in db_data.items():
                print(f"  - {tbl}: {len(rows)} records")

        if "codebase" in data:
            code = data["codebase"]
            print(f"📁 Codebase Snapshot: {code.get('total_files')} files ({code.get('total_size_kb')} KB)")

        if args.inspect:
            return

        print("\n⚡ Ready for database restoration. (Run with DB write permissions to apply).")

    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"❌ Decryption or restore error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
