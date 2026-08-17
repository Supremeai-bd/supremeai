"""bootstrap_sentinel_tables.py

বাংলা: লাইভ Supabase DB-তে SentinelAgent-এর প্রয়োজনীয় টেবিল
(api_endpoints, system_dependencies, system_incidents) তৈরি করে।
এটি Alembic-এর বিকল্প নয় — শুধু ৫০৩ / 'no such table' এরর দ্রুত সারাতে
ORM metadata ব্যবহার করে নির্ভুল DDL তৈরি করে। পূর্ণ মাইগ্রেশন পরে
`alembic upgrade head` দিয়ে করতে হবে।

ব্যবহার: cd backend && python ..\\scripts\\bootstrap_sentinel_tables.py
"""
import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if os.path.abspath(BACKEND) not in [os.path.abspath(p) for p in sys.path]:
    sys.path.insert(0, os.path.abspath(BACKEND))

# .env থেকে DSN পড়া (dotenv ছাড়াই, ম্যানুয়ালি)
ROOT_ENV = os.path.join(os.path.dirname(BACKEND), ".env")
dsn = None
if os.path.exists(ROOT_ENV):
    for line in open(ROOT_ENV, encoding="utf-8"):
        line = line.strip()
        if line.startswith("SUPABASE_DATABASE_URL_POOLER="):
            dsn = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("SUPABASE_DATABASE_URL=") and not dsn:
            dsn = line.split("=", 1)[1].strip().strip('"')

if not dsn:
    raise SystemExit("SUPABASE_DATABASE_URL_POOLER পাওয়া যায়নি .env-এ")

from sqlalchemy import create_engine  # noqa: E402
from models.base import Base  # noqa: E402
import models.sentinel  # noqa: E402  (টেবিলগুলো Base.metadata-এ রেজিস্টার হয়)

engine = create_engine(dsn, future=True)
Base.metadata.create_all(engine, checkfirst=True)
print("[OK] created/verified tables:", sorted(Base.metadata.tables.keys()))
