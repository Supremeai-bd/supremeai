# শূন্য-খরচ সক্ষমতা: এক অ্যাকাউন্ট থেকে কতটা, আর কোথায় থামতে হয়

> উপকরণ: `scripts/ops/zero_cost_capacity_probe.py` · পরীক্ষা: `tests/test_zero_cost_capacity_probe.py`
> সম্পর্কিত: [PR → Production লাইফসাইকেল](../PR_TO_PRODUCTION_LIFECYCLE.md), `gateway/service/free_route_policy.py`, `core/llm/llm_gateway/registry.py`

## ১. মূল কথা: কোটা অ্যাকাউন্টে নয়, **surface**-এ

"একটি Google অ্যাকাউন্ট = ১টি API key, কিন্তু web session দিয়ে আরও ~২.৫ key-এর সমান" — হিসাবটা গঠনগতভাবে ঠিক, কারণ কোটা **surface** ধরে গোনা হয়:

| surface | কোটা কার | সমান্তরালতা | আমাদের কোডে কোথায় |
| --- | --- | --- | --- |
| keyed free tier | প্রতি project/key, RPM + RPD | ✅ সমান্তরাল, RPM বাজেটের ভেতরে | `_ProviderKeyPool` (`registry.py:94` কমা-joined key ভাগ করে, `:127-154` ৪২৯-এ cooldown) |
| web/UI session | অ্যাকাউন্টের ব্রাউজার সেশন | ❌ প্রায় ১টি concurrent op, সিরিয়াল | `AI_FLEET_COOKIES_GZIP_B64`, `BLAZE_SESSION_JWT`, `CHATGPT_SESSION_TOKEN` — `gateway/dual_pool_priority_router.py`-এর `supremeai-web` pool |
| extension surface | ওই ব্রাউজার সেশনই | ❌ সিরিয়াল | এখনও bridge নেই (পরিকল্পনা) |

**তাই গুণ হবে কোটা, throughput নয়।** ৩–৫ গুণ "key-এর সমান" মানে ৩–৫ গুণ *দৈনিক অনুরোধের সীমা*, ৩–৫ গুণ *একসাথে চলা রিকোয়েস্ট* নয়। চ্যাটের streaming TTFT (`gateway/tests/test_stream_first_token_timeout.py`) web surface-এ ধরে রাখা যায় না — তাই web কখনও **শেষ rung**, প্রথম নয়।

## ২. শূন্য-খরচের সিঁড়ি (routing-এর একমাত্র গ্রহণযোগ্য ক্রম)

| rung | কী | নিয়ম |
| --- | --- | --- |
| **L0** | keyed free tier (একাধিক key, comma-joined) | ৪২৯ এলে একটি key cool হয়, pool পরেরটায় যায় — `registry.py`-এ আগেই আছে, শুধু key যোগ করা |
| **L1** | keyed free **vision** roster | ইমেজ প্রথমে এখানেই যাবে; free-tier vision বিদ্যমান থাকলে web session লাগেই না |
| **L2** | web/session bridge (লোকাল পিসি egress) | কেবল L0/L1 শেষ হলে; সিরিয়াল, streaming-গ্যারান্টি নেই, সেশন নীরবে মরে যেতে পারে |
| **L3** | paid | **নিষিদ্ধ** — কখনও নিজে থেকে নির্বাচিত হবে না (`free_route_policy.py`) |

## ৩. চালানো

```bash
# শুধু কনফিগ — নেটওয়ার্ক নেই, secret কখনও প্রিন্ট হয় না
python3 scripts/ops/zero_cost_capacity_probe.py

# লাইভ: models endpoint-এ GET (কোনও টোকেন খরচ হয় না), latency + ALIVE/EXPIRED/CHALLENGED
python3 scripts/ops/zero_cost_capacity_probe.py --live

# machine-readable (ভবিষ্যতের admin dashboard-এর জন্য)
python3 scripts/ops/zero_cost_capacity_probe.py --json

# কোনও keyed surface না থাকলে fail
python3 scripts/ops/zero_cost_capacity_probe.py --strict
```

আউটপুট দুটো টেবিল দেয়: **surface** (key সংখ্যা, অবস্থা, latency) আর **ladder** (কোন rung-এ কোন surface আছে)। `PRESENT` মানে "কনফিগার করা আছে" — `ALIVE` নয়। সেশন জীবিত কি না তা একমাত্র সাইটে সত্যিকারের রিকোয়েস্ট করলেই জানা যায়, আর সেটাই bridge-এর আগের ধাপ।

## ৪. যে তিনটি সীমা মনে রাখতে হবে

1. **Ban concentration:** একই অ্যাকাউন্টে একাধিক project/key বানিয়ে RPD বাড়ানো abuse-policy-র ধারে ঘেঁষে; ban হলে পুরো অ্যাকাউন্ট (এবং তার সাথে যুক্ত সব কিছু) যায়। নিরাপদ ছাদ = অ্যাকাউন্টের স্বাভাবিক surface গুলোই।
2. **Free-tier vision বাস্তব:** ইমেজ মানেই payment নয় — free-tier মাল্টিমোডাল মডেল ও `:free` VL মডেল আছে। তাই ইমেজকে paid ধরে নেওয়া ভুল; আগে L1 যাচাই করুন, তারপরই bridge।
3. **Maintenance = খরচ:** web surface ভাঙে (সাইট বদলায়, challenge বাড়ে)। এটা টাকার বদলে সময়ের খরচ; L2 কে fallback না রেখে primary বানালে প্রতিদিনের কাজ আটকে যাবে।
