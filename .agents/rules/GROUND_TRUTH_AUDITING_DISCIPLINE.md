# 🛡️ Rule: Ground-Truth Evidence & Honest Auditing Discipline

> **Scope:** Always on across SupremeAI workspace and agent interactions.  
> **Source:** Learned from audit error reflection (2026-09-13).  
> **Directives:** Never produce superficial, document-trusting, or unverified audits.

---

## ১. The Core Anti-Patterns to Ban Forever

### ❌ Anti-Pattern ১: Document Text Blind Trust (বাসি ডকুমেন্টে অন্ধ বিশ্বাস)
- **ভুল:** প্ল্যান বা অডিট ফাইলে লেখা আছে "X ফাইল থেকে Y সরান", আর এজেন্ট কোডবেস চেক না করেই বলে দিল "হ্যাঁ, X ফাইল ঠিক করতে হবে"।
- **বাস্তবতা:** ফাইলটি হয়তো ইতিমধ্যে মুছে ফেলা হয়েছে বা কাজ সম্পন্ন হয়েছে (Stale finding)।
- **বাধ্যতামূলক নিয়ম:** যেকোনো অডিট বা পর্যালোচনায় কোনো ফাইলের নাম এলে **প্রথমে `grep_search` বা `view_file` দিয়ে যাচাই করতে হবে যে ফাইলটি বা সিম্বলটি বর্তমান কোডবেসে বাস্তবে বিদ্যমান কি না**।

### ❌ Anti-Pattern ২: Premature Green Flag & Status Desync (`STATUS.md` বনাম `CHECKPOINT.md`)
- **ভুল:** `STATUS.md`-এ "Pending Tasks: None" দেখে ইউজারকে বলা "সব কাজ শেষ", অথচ `CHECKPOINT.md`-এ ১০৩টি টেস্ট স্কিপড এবং একাধিক কাজ পেন্ডিং।
- **বাস্তবতা:** সামারি ফাইলগুলো প্রায়ই আউটডেটেড থাকে এবং মিথ্যা আশ্বাস দেয়।
- **বাধ্যতামূলক নিয়ম:** 
  1. কখনো কেবল একটি স্ট্যাটাস মার্কডাউন ফাইলের দাবিতে বিশ্বাস করা যাবে না।
  2. `STATUS.md` এবং `CHECKPOINT.md`/টেস্ট সুটের মধ্যে অমিল থাকলে স্পষ্ট ভাষায় **"Documentation Desync / False Green Flag"** হিসেবে রিপোর্ট করতে হবে।
  3. গ্রাউন্ড ট্রুথ হবে লাইভ টার্মিনাল রান (`git status`, `git diff`, `pytest`, `ruff`), কোনো মার্কডাউন টেক্সট নয়।

### ❌ Anti-Pattern ৩: Terminal Verification ছাড়া সংখ্যা বা এরর দাবি করা
- **ভুল:** প্ল্যান ডকুমেন্টে লেখা "১৮১টি F821 এরর আছে" বা "১২৬টি ESLint warning আছে", আর এজেন্ট সেটাকেই বর্তমান সত্য ধরে রিপোর্ট করল।
- **বাস্তবতা:** বর্তমান ব্রাঞ্চে ইতোমধ্যে রুলস বা ফিক্স অ্যাড হয়ে সংখ্যা পরিবর্তন হতে পারে।
- **বাধ্যতামূলক নিয়ম:** কোনো এরর বা টেস্ট কাউন্ট নিয়ে কথা বলার আগে টার্মিনালে আসল কমান্ড (`ruff check ...`, `pytest --collect-only`, `pnpm run lint`) এক্সিকিউট করে লাইভ প্রমাণ (Evidence) নিতে হবে।

### ❌ Anti-Pattern ৪: "সব একসাথে ঠিক করার" ওভার-ইঞ্জিনিয়ারিং
- **ভুল:** একবারে সব মাইগ্রেশন ডিলিট করা বা একবারে কভারেজ ৩০% থেকে ৬৫% করার ঝুঁকি নেওয়া।
- **বাস্তবতা:** এতে প্রোডাকশন ভেঙে পড়ে।
- **বাধ্যতামূলক নিয়ম:** সবসময় **Lightweight & Phased** অ্যাপ্রোচ নিতে হবে:
  - Phase 1: Evidence & stale finding cleanup
  - Phase 2: P0 security & tenant isolation
  - Phase 3: Build & test truth
  - Phase 4: Safe architecture cleanup (Baseline snapshot first)

---

## ২. Auditing Checklist (প্রতিটি রিভিউ ও অডিটের আগে বাধ্যতামূলক)

যেকোনো অডিট রিপোর্ট দেওয়ার আগে এজেন্টকে অবশ্যই নিচের ৪টি প্রশ্ন নিশ্চিত করতে হবে:
1. [ ] আমি কি রেফারেন্স ফাইলটি সত্যিই কোডবেসে আছে কি না যাচাই করেছি (`grep_search` / `file exists`)?
2. [ ] আমি কি ডকুমেন্টের দাবিকে সরাসরি টার্মিনাল কমান্ডের আউটপুটের সাথে মিলিয়ে দেখেছি?
3. [ ] আমি কি কোনো মিথ্যা আশ্বাস ("সব পারফেক্ট", "জিরো পেন্ডিং") এড়িয়ে বাস্তব ঝুঁকি ও অমিলগুলো সততার সাথে তুলে ধরেছি?
4. [ ] আমার সুপারিশ কি রিপোজিটরির "Reuse Before Creation" এবং "Zero-Cost Lightweight" ফিলোসফির সাথে সামঞ্জস্যপূর্ণ?
