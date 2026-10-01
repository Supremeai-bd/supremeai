<!-- #2912: Fixed Universal PR Template v2 — সব agent ও মানুষের জন্য একই চুক্তি।
     Template Gate (pr.yml → template_gate.py --pr) এই সেকশনগুলো যাচাই করে:
     ## Summary · ## Linked Issue (Refs #N) · ## Rollback Path
     সেকশন-শিরোনাম অপরিবর্তিত রাখুন — নইলে PR ব্লক হবে। -->

## Summary
<!-- ১–৩ লাইনে: কী বদলালো ও কেন (বাংলা/বাংলিশ) -->

## Linked Issue / Claim
<!-- বাধ্যতামূলক: যে issue claim করে এই কাজ হচ্ছে — ঠিক এই লাইনটি রাখুন -->
Refs #<issue-number>

## Type of Change
- [ ] `fix` — বাগ-ফিক্স
- [ ] `feat` — নতুন ক্যাপাবিলিটি
- [ ] `chore` / `docs` / `refactor` / `test` / `perf` — সাপোর্টিং কাজ

## Touching Files (Scope Boundary)
<!-- ইস্যুতে ঘোষিত ফাইলগুলো — Scope Gate এই তালিকা দিয়েই যাচাই করে -->
- `path/to/file.py`

## Test Evidence (3-Tier যাচাই-চুক্তি)
<!-- ৬-পয়েন্ট যাচাই-চুক্তির (AGENT_RULES.md ভাগ ৪) প্রমাণ -->
1. **Reflection Check:** `git grep -n "<symbol>"` → ফলাফল
2. **Syntax/Boot:** YAML/JSON/Python পার্স + বুট-স্মোক প্রমাণ
3. **Tests:** `pytest <test-file> -v` → পাস-আউটপুট

## Rollback Path
- [ ] `git revert`-নিরাপদ (স্কিমা/ডেটা-মাইগ্রেশন জড়িত নয়)
<!-- স্কিমা/ডেটা বদল থাকলে উপরের চেক বাদ দিয়ে ধাপে-ধাপে রোলব্যাক-পথ লিখুন -->

## Reflection Evidence (why + alternatives_rejected)
<!-- Layer 4/5-only PR-এ বাধ্যতামূলক (#2682); অন্যথায় সংক্ষিপ্ত রাখুন -->
- **why:** …
- **alternatives_rejected:** …
