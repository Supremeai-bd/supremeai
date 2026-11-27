#!/usr/bin/env python3
"""Nightly encrypted Postgres backup for SupremeAI (Supabase prod).

বাংলা মন্তব্য: আগের "backup" রুট শুধু Render-এর ক্ষণস্থায়ী ডিস্কে দুটি ফাইল কপি করত —
রিস্টার্টে মুছে যেত, ডাটাবেস ছিলই না। এই স্ক্রিপ্ট GitHub Actions থেকে প্রতিরাতে চলে:

  1. Infisical থেকে আসা DB URL (pooler হলে session-mode 5432-এ রূপান্তর — pg_dump
     transaction-mode 6543-এ কাজ করে না, আর direct host IPv6-only)
  2. pg_dump --format=custom (public + auth স্কিমা; লগ-টেবিলের *ডেটা* বাদ, স্কিমা থাকে)
  3. openssl AES-256-CBC + PBKDF2 দিয়ে এনক্রিপ্ট (BACKUP_ENCRYPTION_KEY) — কাঁচা ডাম্প
     কখনো artifact-এ যায় না
  4. manifest.json — শুধু মেটাডেটা (আকার, sha256, সময়, টেবিল সংখ্যা), কোনো secret নয়

রিস্টোর (মানুষ-চালিত, ইচ্ছাকৃতভাবে অটো নয়):
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_ENCRYPTION_KEY \\
      -in supremeai-db.dump.enc -out supremeai-db.dump
  pg_restore --no-owner --no-privileges --clean --if-exists -d "$TARGET_DB_URL" supremeai-db.dump
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

DB_URL_ENV_ORDER = ("SUPABASE_DATABASE_URL_POOLER", "SUPABASE_DATABASE_URL_WRITER", "SUPABASE_DATABASE_URL")
SCHEMAS = ("public", "auth")
# বাংলা মন্তব্য: ৭-দিনের retention-যুক্ত লগ টেবিল — স্কিমা রাখি, ডেটা নয় (ডাম্প ছোট থাকে)।
EXCLUDE_TABLE_DATA = ("public.evolution_logs",)
PBKDF2_ITER = 200000
DUMP_NAME = "supremeai-db.dump.enc"
MANIFEST_NAME = "manifest.json"


class BackupError(RuntimeError):
    """Configuration or tool failure with a message that is safe to print."""


def resolve_db_url(env: dict[str, str]) -> tuple[str, str]:
    """Return (url, source_env_name). Never returns or prints the password."""
    for name in DB_URL_ENV_ORDER:
        raw = (env.get(name) or "").strip().strip("\"'")
        if raw:
            return session_mode_url(raw), name
    raise BackupError("No database URL in vault (" + "/".join(DB_URL_ENV_ORDER) + ")")


def session_mode_url(url: str) -> str:
    """Supabase pooler transaction mode (6543) cannot run pg_dump; session mode is 5432 on the same host."""
    parts = urlsplit(url)
    if parts.scheme.startswith("postgres") and parts.port == 6543 and "pooler.supabase.com" in (parts.hostname or ""):
        netloc = parts.netloc.rsplit(":", 1)[0] + ":5432"
        parts = parts._replace(netloc=netloc)
    query = parts.query
    if "sslmode=" not in query:
        query = (query + "&" if query else "") + "sslmode=require"
    return urlunsplit(parts._replace(query=query))


def redact(url: str) -> str:
    """Host/port/db only — for logs."""
    p = urlsplit(url)
    return f"{p.hostname}:{p.port or 5432}{p.path}"


def pg_dump_cmd(url: str, out_file: Path) -> list[str]:
    cmd = ["pg_dump", "--format=custom", "--compress=6", "--no-owner", "--no-privileges",
           f"--file={out_file}", f"--dbname={url}"]
    cmd += [f"--schema={s}" for s in SCHEMAS]
    cmd += [f"--exclude-table-data={t}" for t in EXCLUDE_TABLE_DATA]
    return cmd


def encrypt_cmd(src: Path, dst: Path) -> list[str]:
    return ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", str(PBKDF2_ITER), "-salt",
            "-pass", "env:BACKUP_ENCRYPTION_KEY", "-in", str(src), "-out", str(dst)]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_dump_tables(dump: Path) -> int:
    """`pg_restore --list` TOC → number of TABLE DATA entries (sanity: an empty dump is a failure)."""
    res = subprocess.run(["pg_restore", "--list", str(dump)], capture_output=True, text=True, check=True)
    return sum(1 for line in res.stdout.splitlines() if " TABLE DATA " in line)


def build_manifest(*, encrypted: Path, plain_bytes: int, tables: int, source_env: str,
                   started: datetime, finished: datetime, pg_dump_version: str) -> dict:
    return {
        "kind": "supremeai-db-backup",
        "version": 1,
        "created_at": finished.isoformat(),
        "duration_s": round((finished - started).total_seconds(), 1),
        "file": encrypted.name,
        "encrypted_bytes": encrypted.stat().st_size,
        "plain_bytes": plain_bytes,
        "sha256": sha256_file(encrypted),
        "table_data_entries": tables,
        "schemas": list(SCHEMAS),
        "excluded_table_data": list(EXCLUDE_TABLE_DATA),
        "encryption": f"aes-256-cbc+pbkdf2({PBKDF2_ITER})",
        "db_url_source": source_env,
        "pg_dump": pg_dump_version,
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
    }


def run(out_dir: Path, env: dict[str, str]) -> dict:
    if not (env.get("BACKUP_ENCRYPTION_KEY") or "").strip():
        raise BackupError("BACKUP_ENCRYPTION_KEY missing in Infisical — refusing to write an unencrypted dump")
    url, source = resolve_db_url(env)
    # বাংলা মন্তব্য: শুধু env-নাম লগ হয় — URL/host নয় (CodeQL clear-text-logging নীতি)।
    print(f"[db-backup] db url source={source}")
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    version = subprocess.run(["pg_dump", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "supremeai-db.dump"
        res = subprocess.run(pg_dump_cmd(url, plain), capture_output=True, text=True, check=False)
        if res.returncode != 0:
            # pg_dump stderr never contains the password; trim anyway.
            raise BackupError(f"pg_dump failed (exit {res.returncode}): {res.stderr.strip()[-400:]}")
        tables = count_dump_tables(plain)
        if tables == 0:
            raise BackupError("pg_dump produced no table data — refusing to publish an empty backup")
        encrypted = out_dir / DUMP_NAME
        subprocess.run(encrypt_cmd(plain, encrypted), check=True, env={**os.environ, **env})
        manifest = build_manifest(encrypted=encrypted, plain_bytes=plain.stat().st_size, tables=tables,
                                  source_env=source, started=started, finished=datetime.now(UTC),
                                  pg_dump_version=version)
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="db-backup", help="output directory (artifact root)")
    args = ap.parse_args()
    try:
        manifest = run(Path(args.out), dict(os.environ))
    except BackupError as exc:
        print(f"::error title=db-backup::{exc}")
        return 1
    print(f"::notice title=db-backup::ok tables={manifest['table_data_entries']} "
          f"bytes={manifest['encrypted_bytes']} sha256={manifest['sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
