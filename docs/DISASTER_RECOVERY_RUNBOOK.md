# Disaster Recovery & Supabase Point-in-Time Recovery (PITR) Runbook

**Last Verified:** 2026-11-06  
**Target Database:** Supabase Primary (`https://xtvkltzmberxekoamala.supabase.co`)  
**Target Engine:** PostgreSQL 15+ (PostgREST / Supabase Managed)  
**Status:** Canonical Operations SSOT

---

## ১. ওভারভিউ ও রিকভারি অবজেক্টিভস (RPO & RTO)

| প্যারামিটার | অবজেক্টিভ | বিবরণ |
| :--- | :--- | :--- |
| **RPO (Recovery Point Objective)** | **< ২ মিনিট** | PITR সক্রিয় থাকলে যেকোনো ট্রানজ্যাকশন পয়েন্টে ডাটাবেজ স্টেট রিস্টোর করা যায়। |
| **RTO (Recovery Time Objective)** | **< ১৫ মিনিট** | ড্যাশবোর্ড থেকে নতুন ব্রাঞ্চ/পয়েন্টে রিস্টোর সম্পন্ন হয়ে নতুন সংযোগ পেতে সর্বোচ্চ ১৫ মিনিট সময় লাগে। |

---

## ২. Supabase অটোমেটেড ব্যাকআপ ও PITR পলিসি

Supabase প্রোডাকশনে দুই ধরনের ব্যাকআপ মেকানিজম প্রদান করে:

1. **Daily Automated Backups:**
   - প্রতিদিন স্বয়ংক্রিয়ভাবে পূর্ণাঙ্গ স্ন্যাপশট ব্যাকআপ নেওয়া হয় এবং ৭ থেকে ৩০ দিন পর্যন্ত সংরক্ষিত থাকে।
2. **Point-in-Time Recovery (PITR):**
   - প্রতি মিনিটের WAL (Write-Ahead Logging) স্ট্রিম সংরক্ষিত থাকে, যার ফলে কোনো টেবিল দুর্ঘটনাবশত ডিলিট হলে ঠিক সেই ঘটনার ১ মিনিট আগের মুহূর্তে ফিরে যাওয়া সম্ভব।

---

## ৩. ম্যানুয়াল ও ইমার্জেন্সি রিস্টোরেশন পদ্ধতি (Step-by-Step Drill)

ডাটাবেজে কোনো বিপর্যয় (Data corruption / accidental drop) ঘটলে নিচের ধাপগুলো অনুসরণ করুন:

### ধাপ ১: ইনসিডেন্ট ডিটেকশন ও আইসোলেশন
1. অবিলম্বে ক্ষতিকারক ট্রাফিক বন্ধ করতে Cloudflare বা Gateway-তে সিকিউরিটি ট্রাফিক মিউট করুন:
   ```bash
   # গেটওয়ে রিলে মিউট অথবা টেন্যান্ট এক্সেস সাময়িক ফ্রিজ
   ```
2. ইনসিডেন্ট লগ এবং শেষ পরিচিত ভালো টাইমস্ট্যাম্প (`UTC Timestamp`) নোট করুন।

### ধাপ ২: Supabase ড্যাশবোর্ডে রিস্টোর ইনিশিয়েশন
1. **[app.supabase.com](https://app.supabase.com)**-এ লগইন করে প্রজেক্ট **`SupremeAI Primary`** সিলেক্ট করুন।
2. বাম মেনুর গিয়ার আইকন থেকে **Settings** -> **Database**-এ যান।
3. **Backups** ট্যাবে ক্লিক করুন।
4. **Point in Time** অপশন সিলেক্ট করুন:
   - বিপর্যয় ঘটার পূর্ববর্তী নিরাপদ সময় (যেমন: `2026-11-06 12:15:00 UTC`) নির্ধারণ করুন।
   - **Restore to this point** বাটনে চাপ দিন।
   *(দ্রষ্টব্য: Supabase লাইভ ডাটাবেজকে সরাসরি রিভার্ট করে অথবা একটি নতুন আইসোলেটেড রিস্টোরেশন ডাটাবেজ তৈরি করে দেয়)*।

### ধাপ ৩: কানেকশন স্ট্রিং ও এনভায়রনমেন্ট ভল্ট সিঙ্ক
যদি নতুন কানেকশন স্ট্রিং তৈরি হয়:
1. নতুন `SUPABASE_DATABASE_URL_POOLER` এবং `SUPABASE_DATABASE_URL_WRITER` কপি করুন।
2. Infisical প্রোডাকশন ভল্ট এবং GitHub Secrets-এ নতুন ইউআরএল আপডেট করুন:
   ```bash
   gh secret set SUPABASE_DATABASE_URL_POOLER -R Supremeai-bd/supremeai --body "<NEW_URL>"
   gh secret set SUPABASE_DATABASE_URL_WRITER -R Supremeai-bd/supremeai --body "<NEW_URL>"
   ```

### ধাপ ৪: ডাটাবেজ ইন্টিগ্রিটি ও RLS ভেরিফিকেশন
রিস্টোর সম্পন্ন হওয়ার পর MCP Control Tower থেকে স্কিমা ও কোর টেবিলের উপস্থিতি ভেরিফাই করুন:
```bash
python scripts/ci/schema_contract_check.py
```
যাচাই করুন: `api_keys`, `task_history`, `tenant_limits`, `users`, `conversation_context` সক্রিয় আছে কি না।

---

## ৪. ড্রিঙ্ক ও সিডিউল ভেরিফিকেশন সাইন-অফ
- **ড্রিল ফ্রিকোয়েন্সি:** প্রতি মাসে অন্তত একবার স্ট্যাটিক ব্যাকআপ ফাইল দিয়ে টেস্ট ডেটাবেজে রিস্টোরেশন ড্রিল চালানো বাধ্যতামূলক।
- **রেসপনসিবল রোল:** SRE / Platform Guardian।
