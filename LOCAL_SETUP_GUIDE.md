# 🔱 SupremeAI 2.0 — Local Setup & Execution Guide

এই গাইডটিতে লোকালহোস্টে প্রজেক্ট সেটআপ, রান এবং ডাটাবেজ ইন্টিগ্রেশনের সব ধাপ বিস্তারিত দেওয়া হলো।

---

## 📋 সূচিপত্র (Table of Contents)
1. [Frontend ও Monorepo রান করা](#১-frontend-ও-monorepo-রান-করা)
2. [পোর্ট ও ইন্টারফেসের পার্থক্য](#২-পোর্ট-ও-ইন্টারফেসের-পার্থক্য)
3. [Backend সার্ভার রান করা](#৩-backend-সার্ভার-রান-করা)
4. [Firebase থেকে API Keys ও Credentials সিঙ্ক করা](#৪-firebase-থেকে-api-keys-ও-credentials-সিঙ্ক-করা)

---

## ১. Frontend ও Monorepo রান করা
প্রজেক্টের রুট ডিরেক্টরিতে (`supremeai_2.0`) গিয়ে টার্মিনালে নিচের কমান্ডটি রান করুন:
```bash
npm run dev
```
এটি Turbo Repo ব্যবহার করে একসাথে সব ফ্রন্টএন্ড প্যাকেজ কম্পাইল এবং স্টার্ট করবে।

---

## ২. পোর্ট ও ইন্টারফেসের পার্থক্য
`npm run dev` সফলভাবে রান হওয়ার পর আপনার ব্রাউজারে নিচের সার্ভিসগুলো ওপেন হবে:

* **Web Chat (`http://localhost:5173`)**: এটি সাধারণ ব্যবহারকারীদের জন্য চ্যাটিং ইন্টারফেস। এখানে শুধু চ্যাট উইন্ডো এবং সাধারণ ৩টি আইন দেখতে পাবেন।
* **Studio Client (`http://localhost:5174`)**: এটি ডেভেলপার/এডমিনদের জন্য IDE এবং কন্ট্রোল প্যানেল। এখানে কোড এডিটর এবং এডমিন কনসোল অ্যাক্সেস করা যায়।

---

## ৩. Backend সার্ভার রান করা
যদি চ্যাট করার সময় **"Error connecting to agent backend"** দেখায় বা স্ট্যাটাস বার **Offline** থাকে, তবে ব্যাকএন্ড রান করতে হবে:

1. একটি নতুন টার্মিনাল উইন্ডো খুলুন।
2. ব্যাকএন্ড ডিরেক্টরিতে যান:
   ```bash
   cd backend
   ```
3. লোকাল পাইথন ভার্চুয়াল এনভায়রনমেন্ট ব্যবহার করে সার্ভার চালু করুন:
   ```bash
   .venv\Scripts\python -m uvicorn core.app:app --reload
   ```
সার্ভারটি সফলভাবে চালু হলে টার্মিনালে `INFO: Application startup complete.` লেখা আসবে এবং এটি `http://127.0.0.1:8000` পোর্টে রান হবে।

---

## ৪. Firebase থেকে API Keys ও Credentials সিঙ্ক করা
প্রোডাকশনের মতো রিয়েল সার্ভিস (Supabase, API Keys, GCP) লোকালি কাজ করানোর জন্য ফায়ারস্টোরে সেভ থাকা Credentials রুট `.env` ফাইলে সিঙ্ক করার নিয়ম:

1. রুট ডিরেক্টরিতে `sync_secrets.py` নামে একটি ফাইল তৈরি করে নিচের কোডটি রাখুন:
   ```python
   import firebase_admin
   from firebase_admin import credentials, firestore
   import json
   from pathlib import Path

   # Firebase Initialize
   cred = credentials.Certificate("backend/service-account.json")
   firebase_admin.initialize_app(cred)
   db = firestore.client()

   # Fetch Secrets
   docs = db.collection("system_secrets").document("primary_vault").get()
   vault = docs.to_dict()

   # Parse and update .env
   env_path = Path(".env")
   env_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
   existing_keys = {line.split("=")[0].strip(): idx for idx, line in enumerate(env_lines) if "=" in line and not line.strip().startswith("#")}

   for k, v in vault.items():
       if isinstance(v, str) and (v.startswith("{") or v.startswith("[")):
           continue  # Skip complex json strings for raw env
       val_str = f'"{v}"' if isinstance(v, str) and not v.startswith('"') else str(v)
       if k in existing_keys:
           env_lines[existing_keys[k]] = f"{k}={val_str}"
       else:
           env_lines.append(f"{k}={val_str}")

   # Explicitly set Supabase Project URL
   supabase_url = "https://zxhsevgrdkfvapllqpiw.supabase.co"
   if "SUPABASE_URL" in existing_keys:
       env_lines[existing_keys["SUPABASE_URL"]] = f'SUPABASE_URL="{supabase_url}"'
   else:
       env_lines.append(f'SUPABASE_URL="{supabase_url}"')

   # Save updated .env
   env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
   print("[SUCCESS] Local .env has been synced with Firebase vault!")
   ```

2. স্ক্রিপ্টটি রান করতে টার্মিনালে লিখুন:
   ```bash
   backend\.venv\Scripts\python sync_secrets.py
   ```
   এটি সফলভাবে সম্পন্ন হলে আপনার লোকাল এপিআই কি এবং সার্ভিস অ্যাকাউন্ট রিয়েল ক্লাউডের সাথে কানেক্ট হয়ে যাবে।
