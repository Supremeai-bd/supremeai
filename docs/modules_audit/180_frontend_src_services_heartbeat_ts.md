# Module 180: `frontend/src/services/heartbeat.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/heartbeat.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 40 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // বাংলা মন্তব্য: এটি একটি গ্লোবাল হার্টবিট সার্ভিস, যা প্রতি ১০ মিনিট অন্তর /api/v1/live ইনফ্রাস্ট্রাকচার প্রোব দিয়ে
> // সার্ভারগুলোকে স্লিপিং মোডে যাওয়া থেকে বিরত রাখে। /health থেকে /api/v1/live তে মাইগ্রেটেড
> // কারণ /api/v1/live শুধু প্রসেস লাইভনেস চেক করে, Redis/DB ডিপেন্ডেন্সি টাচ করে না তাই আরো লাইটওয়েট
> // Initial ping 10 seconds after load
> // Ping every 10 minutes
> // বাংলা মন্তব্য: getApiBaseUrl() ব্যবহার করা হচ্ছে যাতে Firebase Hosting-এ relative path ('') পাওয়া যায়
> // এবং firebase.json proxy rewrites দিয়ে সার্ভার-সাইড প্রক্সি হয় — কোনো CORS/preflight ঝামেলা থাকে না।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।
