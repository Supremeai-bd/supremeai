# ⚠️ PENDING MANUAL TASKS (ম্যানুয়ালি করণীয় কাজসমূহ)

*Last updated: 2026-06-20 (Full project re-audit)*

নিচের কাজগুলো কোড বা অটোমেশন দিয়ে সম্পন্ন করা সম্ভব নয়, এগুলো আপনার লোকাল এবং ক্লাউড অ্যাকাউন্টে ম্যানুয়ালি করতে হবে:

## ১. অ্যাকাউন্ট তৈরি ও ডিপ্লয়মেন্ট (Account Creation & Deployment)

| কাজ | স্ট্যাটাস | নোট |
|---|---|---|
| GCP Cloud Run ডিপ্লয়মেন্ট | ✅ সম্পন্ন | `https://supremeai-api-565236080752.us-central1.run.app` লাইভ |
| GCP Services Enablement | ✅ সম্পন্ন | Firestore, Pub/Sub, Cloud Functions সচল |
| Firebase Hosting | ✅ সম্পন্ন | `https://supremeai-a.web.app` লাইভ |
| Sentry DSN সেটআপ | ✅ সম্পন্ন | DSN কী `.env`-এ যুক্ত |
| **Railway.app ডিপ্লয়মেন্ট** | ❌ বাকি | 3-node active-active mesh এর জন্য |
| **Render.com ডিপ্লয়মেন্ট** | ❌ বাকি | ফলব্যাক নোডের জন্য |
| **Supabase অ্যাকাউন্ট** | ❌ বাকি | শেয়ার্ড PostgreSQL DB সেটআপ |
| **Upstash Redis** | ❌ বাকি | শেয়ার্ড টাস্ক কিউ সেটআপ |
| **Cloudflare Workers** | ❌ বাকি | লোড ব্যালেন্সার স্ক্রিপ্ট ডিপ্লয় |
| Make.com / n8n অটোমেশন | ❌ বাকি | ওয়ার্কফ্লো অটোমেশন সেটআপ |

## ২. এনভায়রনমেন্ট কনফিগারেশন (.env Setup)

- [x] OpenRouter, Gemini, DeepSeek, HuggingFace API Keys — সেট করা হয়েছে ✅
- [x] Sentry DSN — সেট করা হয়েছে ✅
- [x] GCP credentials (`GOOGLE_APPLICATION_CREDENTIALS`) — সেট করা হয়েছে ✅
- [ ] **Telegram Bot Token** (BotFather থেকে) — `.env`-এ সেট করা বাকি
- [ ] **Discord Bot Token** — `.env`-এ সেট করা বাকি
- [ ] **Supabase** connection string — অ্যাকাউন্ট তৈরির পর সেট করা হবে
- [ ] **Upstash Redis** URL — অ্যাকাউন্ট তৈরির পর সেট করা হবে
- [ ] **Railway/Render** deployment URL — ডিপ্লয়ের পর update করতে হবে

## ৩. ইনফ্রাস্ট্রাকচার কাজ (Infrastructure Remaining)

- [ ] **Terraform IaC**: GCP/Firebase রিসোর্সের জন্য `infrastructure/terraform/` স্ক্রিপ্ট তৈরি।
- [ ] **Cloudflare Workers Load Balancer**: GCP(40%), Railway(35%), Render(25%) weight সেট করে লোড ব্যালেন্সার ডিপ্লয়।
- [ ] **GitHub Secrets**: `GCP_SA_KEY`, `GCP_PROJECT_ID` রিপোজিটরিতে সেট করা (CI/CD auto-deploy এর জন্য)।

## ৪. ম্যানুয়াল টেস্টিং (Manual Testing Required)

- [ ] **Voice Interface লাইভ টেস্ট**: Whisper STT + gTTS TTS-এ রিয়েল অডিও ইনপুট/আউটপুট ভেরিফিকেশন।
- [ ] **Telegram/Discord Bot**: লাইভ চ্যাটে বট রেসপন্স যাচাই।
- [ ] **Multi-Cloud Failover**: একটি নোড বন্ধ করে অন্য নোডে অটো-সুইচ যাচাই।

---
*নোট: GCP, Firebase, এবং GitHub CI/CD সফলভাবে সম্পন্ন ও ভেরিফাই করা হয়েছে।*

---
*Last Synced: 2026-06-20 (Full project re-audit)*

<!-- Synced: 2026-06-20 (Full project re-audit — added manual testing section, updated status table) -->
