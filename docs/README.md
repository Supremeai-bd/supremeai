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

### ১. `docs/08-roadmap/` (Roadmap & Status Files)

* **`PROJECT_STATUS.md`**: সম্পূর্ণ প্রজেক্টের লাইভ স্ট্যাটাস ওভারভিউ। এতে প্রতিটি মডিউল লাইভ নাকি scaffold অবস্থায় আছে তার সংক্ষিপ্ত তালিকা থাকবে।
* **`partially_completed_tasks.md` (আংশিক সম্পন্ন কাজ):** 
  - **শুধুমাত্র** সেই কাজগুলো থাকবে যেগুলোর কোডবেজ আংশিক সম্পন্ন কিন্তু কোনো কনফিগারেশন বা এপিআই কী সেটআপ বাকি।
  - **⚠️ কঠোর নিয়ম (Strict Rule):** কোনো কাজ ১০০% সম্পন্ন হওয়ার সাথে সাথে তা **অবশ্যই** এই ফাইল থেকে চিরতরে মুছে ফেলতে হবে এবং `100%_completed_tasks.md` ফাইলে স্থানান্তর করতে হবে।
* **`100%_completed_tasks.md` (সম্পূর্ণ শেষ হওয়া কাজ):** ১০০% শেষ হওয়া কাজের বিস্তারিত বিবরণ থাকবে।
* **`manual_work_needed.md`**: এডমিন বা ডেভেলপারের জন্য পেন্ডিং ম্যানুয়াল কাজগুলো (যেমন: Discord Bot Token জেনারেট করা) এখানে থাকবে। কাজ শেষ হলে এন্ট্রি মুছে যাবে।
* **`test_coverage_and_strategy.md`**: বর্তমান টেস্টের পাস/ফেইল ওভারভিউ এবং ১০০% কভারেজ অর্জনের জন্য কোন ফাইলে টেস্ট বাকি তা ট্র্যাক করবে।

### ২. `docs/04-development/` (Plans & Guides)
* **`master_work_and_implementation_plan.md`**: এটি প্রজেক্টের চলমান রোডম্যাপ।
  - এখানে আংশিক সম্পন্ন `[/]` বা পেন্ডিং `[ ]` কাজগুলোর রূপরেখা থাকবে।
  - কোনো কাজ ১০০% সম্পন্ন হয়ে গেলে এই ফাইলের একটিভ সেকশন থেকে মুছে ফেলে `100%_completed_tasks.md`-এ সোর্স হিসেবে ট্র্যাক করা হবে।

---
*Last Synced: 2026-06-21 (Reorganized document definitions and lifecycles added)*

