# SEC-PLAN — GitHub Token Canonicalization & De-duplication Plan

> **সম্পর্কিত অডিট:** Issue #699 (Finding 3: Master service key + compatibility alias) · Issue #773 · Issue #774  
> **উদ্দেশ্য:** প্ল্যাটফর্ম থেকে দ্বৈত `SUPREMEAI_GITHUB_TOKEN` কী সম্পূর্ণরূপে অপসারন করে একক ক্যানোনিকাল **`GITHUB_TOKEN`** প্রতিষ্ঠা করা। এর ফলে সিক্রেট রোটেশন, অডিট এবং পারমিশন ম্যানেজমেন্ট ১০০% একক সূত্রে (Single Source of Truth) পরিচালিত হবে।

---

## 🎯 ১. সারসংক্ষেপ ও পটভূমি (Executive Summary)

অতীতে প্ল্যাটফর্মে দুটি সমান্তরাল কী ব্যবহৃত হতো:
1. `GITHUB_TOKEN`: প্রাথমিকভাবে রিড-অনলি Fine-grained PAT।
2. `SUPREMEAI_GITHUB_TOKEN`: রেন্ডার ক্লাউড ও অটো-পিআর জেনারেটরের জন্য ব্যবহৃত ক্লাসিক PAT (যা অডিট #773-এ বাতিল করা হয়)।

দুইটি ভিন্ন কী থাকার কারণে কোন এজেন্ট বা সার্ভিস কোন টোকেন দিয়ে কাজ করছে তা নিয়ে বিভ্রান্তি এবং পারমিশন ড্র্রিফ্ট (Permission Drift) তৈরি হচ্ছিল। এই প্ল্যানের মাধ্যমে `SUPREMEAI_GITHUB_TOKEN` সম্পূর্ণ অবসর দেওয়া হবে এবং সমস্ত ক্লাউড নোড, সিআই স্ক্রিপ্ট ও এআই এজেন্ট একক শক্তিশালী `GITHUB_TOKEN` ব্যবহার করবে।

---

## 🔑 ২. একক ক্যানোনিকাল টোকেনের স্পেসিফিকেশন

* **টোকেন নেম (Canonical Name):** `GITHUB_TOKEN`
* **টোকেন টাইপ:** GitHub Fine-Grained Personal Access Token (PAT v2)
* **রিপোজিটরি স্কোপ:** শুধুমাত্র `SaifulHaqueNiloy/supremeai`
* **প্রয়োজনীয় পারমিশন ম্যাট্রিক্স:**
  * **Issues:** `Read and write` 🔴 *(লেবেল অ্যাসাইন, স্ট্যাটাস আপডেট ও ইস্যু ট্র্যাকিং)*
  * **Pull requests:** `Read and write` 🔴 *(PR তৈরি, লেবেল পরিবর্তন ও অটো-রিভিউ)*
  * **Contents:** `Read and write` *(ব্রাঞ্চ তৈরি ও কমিট পুশ)*
  * **Workflows:** `Read and write` *(ঐচ্ছিক — সিআই ওয়ার্কফ্লো ট্রিগার)*

---

## 🌐 ৩. থার্ড-পার্টি প্ল্যাটফর্ম অডিট ফলাফল (Live 3rd-Party Audit Results)

লাইভ API কল ও ক্লাউড কনফিগারেশন স্ক্যানের মাধ্যমে প্রাপ্ত প্রকৃত চিত্র:

| প্ল্যাটফর্ম / সার্ভিস | স্কোপ / সার্ভিস নাম | `SUPREMEAI_GITHUB_TOKEN` উপস্থিতি | `GITHUB_TOKEN` উপস্থিতি | অ্যাকশন প্রয়োজন |
|---|---|---|---|---|
| **Render (Node 4)** | `supremeai-mcp-tower` (srv-d3...) | 🟢 **মুছে ফেলা হয়েছে (DELETED)** | 🟢 **হ্যাঁ (Updated)** | সম্পন্ন (একক GITHUB_TOKEN সক্রিয়) |
| **Render (Node 1)** | `supremeai-primary-node` | ⚪ নেই | ⚪ নেই | কোনো পরিবর্তন নেই |
| **Render (Node 2)** | `supremeai-worker-node` | ⚪ নেই | ⚪ নেই | কোনো পরিবর্তন নেই |
| **Render (Node 3)** | `supremeai-scraper-node` | ⚪ নেই | ⚪ নেই | কোনো পরিবর্তন নেই |
| **Infisical Vault** | `prod` / `staging` / `dev` | 🟢 **না (404/Purged)** | 🟢 **হ্যাঁ (Updated)** | সম্পন্ন (শুধু GITHUB_TOKEN আছে) |
| **GitHub Secrets** | `SaifulHaqueNiloy/supremeai` | ⚪ নেই | ⚪ নেই (Native) | কোনো পরিবর্তন নেই |
| **Cloudflare** | Workers / KV / Pages | ⚪ নেই | ⚪ নেই | কোনো পরিবর্তন নেই |
| **Vercel** | Frontend Deployments | ⚪ নেই | ⚪ নেই | কোনো পরিবর্তন নেই |
| **Supabase / Upstash** | DB / Cache Services | ⚪ নেই | ⚪ নেই | কোনো পরিবর্তন নেই |

> 📌 **সারসংক্ষেপ:** ৩য় পক্ষ প্ল্যাটফর্মগুলোর মধ্যে Render Node 4 (`supremeai-mcp-tower`) থেকে `SUPREMEAI_GITHUB_TOKEN` সফলভাবে ডিলিট করে একক `GITHUB_TOKEN` সক্রিয় করা হয়েছে।

---

## 📋 ৪. পূর্ণাঙ্গ বাস্তবায়ন ও পরিবর্তন চেকলিস্ট

### ক. কোডবেস সংশোধন (Source Code)
- [x] **`backend/tools/code/auto_pr_pipeline.py` (লাইন ২৬ ও ৪৯):**
  - লাইন ২৬-এ `or os.getenv("SUPREMEAI_GITHUB_TOKEN", "")` বাদ দিয়ে কেবল `github_token or os.getenv("GITHUB_TOKEN", "")` রাখা হয়েছে।
  - লাইন ৪৯-এ এরর মেসেজ আপডেট করা হয়েছে: `"AutoPRPipeline: No GitHub token configured. Set GITHUB_TOKEN."`
- [x] **`scripts/devops/_audit.py` (লাইন ৬৭):**
  - অডিট ভ্যালিডেটর ডিকশনারি থেকে `"SUPREMEAI_GITHUB_TOKEN": github_v` লাইনটি সম্পূর্ণ মুছে ফেলা হয়েছে।
- [x] **`secrets_registry.yaml` (লাইন ১০১৬):**
  - `SUPREMEAI_GITHUB_TOKEN` কনফিগ এন্ট্রিটি একক `GITHUB_TOKEN`-এ ইউনিফাইড করা হয়েছে।

### খ. ক্লাউড ও ইনফ্রাস্ট্রাকচার (Infisical & Render)
- [x] **Infisical Cloud Vault (`prod`):**
  - `GITHUB_TOKEN` সিক্রেটে নতুন তৈরি করা Fine-grained PAT-টি সফলভাবে আপডেট করা হয়েছে।
  - `SUPREMEAI_GITHUB_TOKEN` ভল্টে নেই (ইতিমধ্যে পার্জড/অনুপস্থিত)।
- [x] **Render Node 4 (`supremeai-mcp-tower`):**
  - রেন্ডার API দিয়ে `supremeai-mcp-tower` সার্ভিস থেকে `SUPREMEAI_GITHUB_TOKEN` সফলভাবে ডিলিট করা হয়েছে এবং `GITHUB_TOKEN` নতুন টোকেনে আপডেট করা হয়েছে।
- [x] **Render Account 2 (`ecosystem-test-core-v2`):**
  - `GITHUB_TOKEN` নতুন টোকেন দিয়ে রেন্ডার এপিআই-এর মাধ্যমে আপডেট করা হয়েছে।
- [x] **লোকাল এনভায়রনমেন্ট (`.env` ও Desktop `env.txt`):**
  - `SUPREMEAI_GITHUB_TOKEN` সম্পূর্ণ রিমুভ করা হয়েছে এবং শুধুমাত্র নতুন `GITHUB_TOKEN` সক্রিয় রাখা হয়েছে।
- [x] **লোকাল GitHub CLI (`gh`):**
  - নতুন টোকেন দিয়ে সফলভাবে রি-অথেনটিকেটেড (`gh auth login`).

### গ. ডকুমেন্টেশন ও স্পেসিফিকেশন সিঙ্ক
- [x] **`docs/deployment/SUPREMEAI_CLUSTER_MASTER_ENV_SPEC.md` (লাইন ১২৬):**
  - `SUPREMEAI_GITHUB_TOKEN` এন্ট্রি মুছে ফেলে একক `GITHUB_TOKEN` তালিকাভুক্ত করা হয়েছে।
- [x] **`docs/security/CREDENTIAL_ROTATION_CHECKLIST.md` (লাইন ৪৩):**
  - সেকশন ১-এর রেফারেন্স আপডেট করে একক `GITHUB_TOKEN` উল্লেখ করা হয়েছে।
- [x] **`docs/reference/THIRD_PARTY_SERVICES.md` (লাইন ৬২৪ ও ৬২৭):**
  - বাতিল টেবিল রো এবং ফুটনোট আপডেট করে একক ক্যানোনিকাল টোকেন হিসেবে সংরক্ষণ করা হয়েছে।

---

## 🧪 ৫. ভেরিফিকেশন ও হেলথ-চেক রানবুক

পরিবর্তন সম্পন্ন করার পর নিচের কমান্ডগুলো চালিয়ে কানেক্টিভিটি নিশ্চিত করা হয়েছে:

1. **টোকেন আইডেন্টিটি ও ভ্যালিডিটি চেক:**
   ```bash
   curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user | grep login
   # Output: "login": "SaifulHaqueNiloy" (200 OK)
   ```
2. **রিপোজিটরি পারমিশন ভেরিফিকেশন:**
   ```bash
   curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/repos/SaifulHaqueNiloy/supremeai | grep -A 5 '"permissions"'
   # Output: admin: true, push: true, pull: true (Full Access)
   ```
3. **লেবেল ও ইস্যু রাইট পারমিশন টেস্ট (PR Helper Guard):**
   ```bash
   gh issue view 803 --json state,labels
   # Successfully closed Issue #803 with resolved label verification
   ```
4. **ক্লাউড প্ল্যাটফর্ম সিঙ্ক ভেরিফিকেশন:**
   - **Render Node 4 (`supremeai-mcp-tower`):** `SUPREMEAI_GITHUB_TOKEN` ভেরিয়েবল সম্পূর্ণ মুছে ফেলা হয়েছে এবং `GITHUB_TOKEN` নতুন ফাইন-গ্রেইন্ড PAT দিয়ে রিপ্লেস করা হয়েছে।
   - **Infisical Cloud Vault (`prod`):** `GITHUB_TOKEN` নতুন ভ্যালুতে আপডেট হয়েছে; `SUPREMEAI_GITHUB_TOKEN` পার্জড।

---
*ডকুমেন্ট আইডি: SEC-PLAN-01 · সুপ্রিমএআই কোর আর্কিটেকচার টিম · সেপ্টেম্বর ২০২৬*
