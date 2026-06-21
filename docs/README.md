# 🔱 SupremeAI 2.0 Documentation Index

Welcome to the SupremeAI 2.0 Documentation. This numbered structure ensures all project design patterns, operations, testing, and roadmaps are organized and accessible.

## 🗺️ Navigation Map

- **[00-meta/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/00-meta)**: Writing guidelines and meta templates.
- **[01-project/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/01-project)**: Product vision, goals, and technology comparisons.
- **[02-governance/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/02-governance)**: AI behaviors, rules, ethics, and PR guidelines.
- **[03-architecture/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/03-architecture)**: System architecture design blueprints and ADR logs.
- **[04-development/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/04-development)**: Onboarding guide, local setup, and master implementation plans.
- **[05-operations/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/05-operations)**: Deployments, monitors, runbooks, and Cloud provisioning.
- **[06-api/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/06-api)**: Endpoint specs, webhooks, and interface contracts.
- **[07-testing/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/07-testing)**: Testing strategy, mocking setups, and coverage guidelines.
- **[08-roadmap/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/08-roadmap)**: PROJECT_STATUS tracking and release logs.
- **[09-security/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/09-security)**: Secrets management, threat model, and incident responses.
- **[10-troubleshooting/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/10-troubleshooting)**: FAQs and common run errors/mitigations.

---

## 📋 Document Lifecycle & Data Guidelines (নথি ব্যবহারের নির্দেশিকা)

প্রতিটি ফাইলে কী ধরনের ডেটা থাকবে এবং কীভাবে আপডেট হবে তা নিচে নির্ধারণ করে দেওয়া হলো:

### ০. `docs/00-meta/` (মেটা গাইডলাইন)
* **ফাইল টাইপ:** `doc-style-guide.md`, `template-adr.md` ইত্যাদি।
* **বিবরণ:** ডকুমেন্টেশন লেখার নিয়ম ও মেটা টেমপ্লেট থাকবে। প্রজেক্টের রাইটিং স্টাইল পরিবর্তন হলে এটি আপডেট হবে।

### ১. `docs/01-project/` (প্রজেক্ট ভিশন ও টার্গেট)
* **ফাইল টাইপ:** `vision.md`, `goals.md`, `supremeai_tech_comparison.csv` ইত্যাদি।
* **বিবরণ:** প্রজেক্টের ভিশন, OKRs ও স্টেকহোল্ডারদের তথ্য থাকবে। প্রতি কোয়ার্টারে লক্ষ্য অর্জনের পর এটি আপডেট হবে।

### ২. `docs/02-governance/` (শাসন ও আচরণ বিধি)
* **ফাইল টাইপ:** `.antigravityrules`, `admin_rules_and_guidelines.md` ইত্যাদি।
* **বিবরণ:** এজেন্টদের আচরণবিধি, AI এথিক্স ও রুলস থাকবে। এডমিন নতুন গাইডলাইন বা রুলস সেট করলে এটি সাথে সাথে আপডেট হবে।

### ৩. `docs/03-architecture/` (সিস্টেম আর্কিটেকচার)
* **ফাইল টাইপ:** `system-overview.md`, ADR (Architecture Decision Records) ইত্যাদি।
* **বিবরণ:** আর্কিটেকচার ডায়াগ্রাম এবং কেন নির্দিষ্ট প্রযুক্তি বেছে নেওয়া হলো তার রেকর্ড থাকবে। বড় কোনো প্রযুক্তিগত পরিবর্তন বা ব্যাকএন্ড রি-রাইট করার আগে ADR যুক্ত হবে।

### ৪. `docs/04-development/` (ডেভেলপমেন্ট ও মাস্টার প্ল্যান)
* **ফাইল টাইপ:** `local-setup.md`, `master_work_and_implementation_plan.md` ইত্যাদি।
* **বিবরণ:** লোকাল অনবোর্ডিং গাইড এবং চলমান একটিভ রোডম্যাপ এখানে থাকবে। নতুন ডেভেলপার যুক্ত হলে বা একটিভ টাস্ক স্ট্যাটাস বদলালে এটি সাথে সাথে আপডেট করতে হবে।

### ৫. `docs/05-operations/` (ডেপ্লয়মেন্ট ও অপারেশনস)
* **ফাইল টাইপ:** `deployment-overview.md`, GCP/Supabase সেটআপ গাইড।
* **বিবরণ:** ক্লাউড ডেপ্লয়মেন্ট রানবুক এবং মনিটরিং গাইডলাইন থাকবে। ইনফ্রাস্ট্রাকচারে কোনো পরিবর্তন (যেমন নতুন ক্লাউড নোড অ্যাড করা) হলে এটি আপডেট হবে।

### ৬. `docs/06-api/` (এপিআই স্পেসিফিকেশন)
* **ফাইল টাইপ:** OpenAPI Spec (`openapi-spec.yaml`), API Endpoint ডক।
* **বিবরণ:** সমস্ত এপিআই এন্ডপয়েন্ট ও প্যারামিটার ডিটেইলস থাকবে। নতুন এপিআই এন্ডপয়েন্ট যুক্ত হলে বা রিকোয়েস্ট স্কিমা পরিবর্তন হলে এটি আপডেট হবে।

### ৭. `docs/07-testing/` (টেস্টিং গাইড ও কভারেজ)
* **ফাইল টাইপ:** `testing-strategy.md` ইত্যাদি।
* **বিবরণ:** ফ্রন্টএন্ড, ব্যাকএন্ড ও মোবাইল অ্যাপের টেস্টিং ও মকিং কৌশল থাকবে। নতুন টেস্ট মডিউল বা কভারেজ গেট টাইমিং পরিবর্তন হলে এটি আপডেট হবে।

### ৮. `docs/08-roadmap/` (টাস্ক ট্র্যাকিং ও রিলিজ)
* **ফাইল টাইপ:** `PROJECT_STATUS.md`, `partially_completed_tasks.md`, `100%_completed_tasks.md`, `manual_work_needed.md`।
* **বিবরণ:**
  - **`partially_completed_tasks.md`:** কাজ ১০০% শেষ হওয়ামাত্রই এই ফাইল থেকে এন্ট্রি চিরতরে মুছে ফেলতে হবে এবং `100%_completed_tasks.md`-এ স্থানান্তর করতে হবে।
  - **`PROJECT_STATUS.md`:** প্রতি কাজের শেষে সামগ্রিক ফিচার ও লাইভ নোড স্ট্যাটাস আপডেট হবে।
  - **`manual_work_needed.md`:** এডমিনের জন্য পেন্ডিং ম্যানুয়াল কাজগুলো থাকবে।

### ৯. `docs/09-security/` (সিকিউরিটি ও সিক্রেট ম্যানেজমেন্ট)
* **ফাইল টাইপ:** `threat-model.md`, `secrets-management.md`।
* **বিবরণ:** প্রজেক্টের সিকিউরিটি থ্রেট, সিক্রেট স্টোরেজ এবং ইনসিডেন্ট রেসপন্স প্রটোকল থাকবে। সিক্রেট রোটেশন পলিসি বা নতুন থ্রেট আইডেন্টিফাই হলে এটি আপডেট হবে।

### ১০. `docs/10-troubleshooting/` (সমস্যা সমাধান)
* **ফাইল টাইপ:** `ci-failures.md`, FAQ।
* **বিবরণ:** কমন এরর, CI/CD পাইপলাইন ফেইল রিকভারি এবং সমাধান থাকবে। নতুন কোনো বাগ বা এররের মুখোমুখি হয়ে তা সমাধান করলে এখানে ডকুমেন্ট করা হবে।

---
*Last Synced: 2026-06-21 (Reorganized document definitions and lifecycles added)*
