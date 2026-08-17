# SupremeAI — ডেভেলপমেন্ট গাইডলাইন সূচি

> এই গাইডলাইনগুলো SupremeAI প্রজেক্টে কাজ করা সকল ডেভেলপারের জন্য।
> নতুন ডেভেলপার থেকে শুরু করে অভিজ্ঞ — সবার কাজে লাগবে।

---

## গাইডলাইন তালিকা

| ফাইল | বিষয় | কার জন্য |
|---|---|---|
| [01-PROJECT-SETUP.md](./01-PROJECT-SETUP.md) | রিপো স্ট্রাকচার, pyproject.toml, git convention | সবার জন্য |
| [02-TESTING-STRATEGY.md](./02-TESTING-STRATEGY.md) | pytest, conftest, mock pattern, coverage | সবার জন্য |
| [03-CI-CD-PIPELINE.md](./03-CI-CD-PIPELINE.md) | GitHub Actions, workflow, deploy gate | Junior → Senior |
| [04-SECURITY-HARDENING.md](./04-SECURITY-HARDENING.md) | JWT, RBAC, input validation, secrets | সবার জন্য |
| [05-BACKEND-ARCHITECTURE.md](./05-BACKEND-ARCHITECTURE.md) | Layered arch, FastAPI, async, caching | Backend dev |
| [06-FRONTEND-DEVELOPMENT.md](./06-FRONTEND-DEVELOPMENT.md) | React, TypeScript, Vitest, state management | Frontend dev |
| [07-DATABASE-MIGRATIONS.md](./07-DATABASE-MIGRATIONS.md) | SQLAlchemy, Alembic, migration safety | Backend dev |

---

## ১০টি সবচেয়ে গুরুত্বপূর্ণ নিয়ম

1. **`testpaths`** — CI `working-directory: backend` থেকে চালালে `testpaths = ["tests"]` — `"backend/tests"` নয়
2. **`--import-mode=importlib`** — duplicate filename collision এড়াতে addopts-এ সবসময় রাখুন
3. **`__init__.py`** — প্রতিটা test subfolder-এ আবশ্যক
4. **Silent failure নিষিদ্ধ** — `except: pass` কখনো নয়; exception log করুন অথবা re-raise করুন
5. **Hardcoded secret নিষিদ্ধ** — সব secret `settings.<field>` থেকে, `.env` ফাইলে
6. **Deploy gate** — `needs: test` ছাড়া deploy job চলবে না; `|| true` দিয়ে failure লুকাবেন না
7. **Coverage threshold** — `pyproject.toml` এবং CI command-এ একই threshold; CI-তে override নয়
8. **`dependency_overrides` reset** — FastAPI test-এ override করলে teardown-এ অবশ্যই `= {}` করুন
9. **`DROP TABLE` বিপজ্জনক** — production-এ কখনো নয়; Alembic migration দিয়ে schema পরিবর্তন
10. **Fail-closed auth** — Exception হলে deny করুন, `except: return {"role": "admin"}` ভয়ংকর

---

## নতুন ডেভেলপার — কোথা থেকে শুরু করবেন

```bash
# ১. রিপো clone করুন
git clone https://github.com/paykaribazaronline/supremeai.git
cd supremeai

# ২. Backend সেটআপ
cd backend
poetry install
cp .env.example .env  # তারপর .env এ real values দিন

# ৩. টেস্ট চালান
poetry run pytest -q

# ৪. Development server
poetry run uvicorn core.app:app --reload --port 8080

# ৫. গাইডলাইন পড়ুন
# 01-PROJECT-SETUP.md → 02-TESTING-STRATEGY.md → আপনার কাজের area
```

---

## PR চেকলিস্ট (সব PR-এ)

```
[ ] টেস্ট পাস: poetry run pytest -q
[ ] Coverage 75%+: poetry run pytest --cov=core --cov-fail-under=75
[ ] Hardcoded secret নেই
[ ] Silent `except: pass` নেই
[ ] নতুন function-এ টেস্ট আছে (happy path + error path)
[ ] নতুন test subfolder-এ __init__.py আছে
[ ] Commit message: Conventional Commits format
```
