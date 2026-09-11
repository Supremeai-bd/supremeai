# Module 205: `frontend/src/store/index.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/index.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 59 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> /**
> * R13 FIX: Unified Store Entry Point
> *
> * When UNIFIED_STORE=true env (or localStorage flag) is set, this file
> * re-exports the unified store under the names of the 12 legacy store hooks.
> * Existing imports `import { useChatStore } from '@/store/chatStore'` keep
> * working UNCHANGED because each legacy store file will be replaced with a
> * 1-line re-export shim in Phase 2.


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।
