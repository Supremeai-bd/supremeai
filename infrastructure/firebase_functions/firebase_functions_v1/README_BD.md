# functions/ ফোল্ডার গাইড

## উদ্দেশ্য

এই ফোল্ডারটি Firebase Cloud Functions কোড ধারণ করে, যা SupremeAI-র সার্ভার-সাইড লজিক হ্যান্ডেল করে।

## ফোল্ডার স্ট্রাকচার

```
functions/
├── lib/           # ফায়ারবেস ফাংশনগুলো
├── node_modules/  # নোড মডিউল
├── package.json   # ফাংশন প্যাকেজ
└── tsconfig.json  # টাইপস্ক্রিপ্ট কনফিগ
```

## মূল ফাংশনগুলো

| ফাংশন                   | ব্যবহার                      |
| ----------------------- | ---------------------------- |
| `api-router.js`         | API রাউটিং                   |
| `health-smart.js`       | সিস্টেম হেলথ চেক             |
| `deployment-monitor.js` | ডিপ্লোয়মেন্ট মনিটরিং        |
| `providers-smart.js`    | AI প্রোভাইডার্স ম্যানেজমেন্ট |

## ডিপ্লোয় করা

```bash
# ফাংশন ডিপ্লোয় করন
firebase deploy --only functions
```

## লোকালি রান

```bash
# ফায়ারবেস ইমুলেটর
firebase emulators:start --only functions
```
