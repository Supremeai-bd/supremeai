# MISSION CONTROL — HYBRID BOUNDARY PROBE (Roadmap §9)

**Status:** Evidence-probe complete (docs-only; zero runtime code touched)
**Source of truth:** monolith `main` @ probe-time (mirror: `paykaribazaronline/supremeai`)
**Discipline:** ভাই-প্রতিম Phase 0 + Phase 6-7 probe ডক; Core-freeze অটুট
**Decision style:** value-driven separation — extraction নয়, boundary-রায় প্রমাণ

---

## ০. এক-লাইন রায়

**Mission Control ইতোমধ্যে §9-এর recommended architecture মেনেই জন্মেছে** (UI → auth-gate →
tool-allowlist → tower)। Hybrid boundary "stabilize" করা মানে নতুন কিছু তৈরি নয় —
বিদ্যমান সীমানার শ্রেণিবিন্যাস লিপিবদ্ধ করা + extraction-বিরতির প্রমাণ দেওয়া।

---

## ১. প্রত্যক্ষ প্রমাণ (monolith probe @ `apps/mission-control`, 110 ফাইল)

### ১.১ চার-স্তরের বাস্তব ম্যাপ (§9 diagram বনাম কোড)

| §9 স্তর | বাস্তব রূপ (কোডে) | প্রমাণ |
|---|---|---|
| Mission Control UI | `src/app/page.tsx` + dashboard shell, unlock-flow, journal, matrix-history views | `src/app/**` |
| Public/Versioned SDK | **নেই** — UI সরাসরি own `/api/*`-তে কথা বলে (এটিই একমাত্র গ্যাপ; §৩ দ্রষ্টব্য) | — |
| Authenticated private gateway | `MISSION_CONTROL_API_TOKEN` → HMAC-signed HttpOnly unlock-cookie (12h TTL), `/api/*` middleware gate | `src/app/api/auth/unlock/route.ts` (FE-10, upstream issue #503) |
| MCP Control Plane / Core | `lib/tower-client` → mcp-tower; **tool-allowlist defense-in-depth** (family-prefix bounded, `TOWER_TOOL_ALLOWLIST` দিয়ে operator-tightenable) | `src/app/api/tower/call/route.ts` |

### ১.২ Privileged পৃষ্ঠ (§9 "Private" শ্রেণিতে পড়ে)

- `api/tower/{call,tools,wake}` — টাওয়ার-নির্দেশ (allowlist-বাউন্ডেড)
- `api/git/{sync,status,ci,sync-log}` — রেপো-অপারেশন
- `api/watchdog/{drill,history}` — self-heal প্রশাসন
- `api/settings`, `api/journal`, `api/events`, `prisma/schema.prisma` — operational data
- `lib/api-auth` — token/cookie স্বাক্ষর (secret-bearing)

### ১.৩ §9 "Public/open candidate" শ্রেণি-প্রার্থী (extraction-এর দিন এলে)

- dashboard shell components, visualizations, generic system views
- (studio-র `e2e/commandcenter.spec.ts` প্রমাণ করে command-center UX ইতোমধ্যে
  studio-পাশেও বাস করে — ভবিষ্যৎ extraction-এর প্রাকৃতিক বীজ)

---

## ২. রায় ও অজুহাতহীন সততা

1. **Extraction এখনই নয়** — Phase 6-7 probe-র রায়ের মতোই: সীমানা স্থাপত্যগতভাবে সঠিক,
   কিন্তু স্বাধীন জীবনের (standalone deploy) প্রয়োজন আজ নেই। জটিলতা-হ্রাস নীতি।
2. **একটি সত্যিকারের গ্যাপ রয়েছে**: UI কোনো versioned SDK ব্যবহার করে না —
   চুক্তি সরাসরি own-route-এ বাঁধা। ভবিষ্যৎ-কাজ (extraction-পূর্বশর্ত): tower-call
   চুক্তিটি SDK-র typed surface-এ ওঠা। আজ এটি করা হয়নি — কারণ Core-freeze +
   কোনো দ্বিতীয় consumer নেই (নকল abstraction নিষিদ্ধ)।
3. **প্রমাণ-মান**: প্রতিটি দাবি উপরের টেবিলে ফাইল-স্তরে বাঁধা; কোনো aspiration-দাবি নেই।

---

## ৩. পরবর্তী-সম্ভাব্য (এই প্রোব থেকে বেরিয়ে আসা নিবন্ধিত প্রার্থী)

- upstream research-ডক মনিটর (memory-governance → tower-চুক্তির প্রভাব)
- tower-call SDK-চুক্তি: শুধু যখন ২য় consumer জন্মাবে (দু-ক্লায়েন্ট নিয়ম)
- public-candidate component-গুলির তালিকা studio-র সাথে সংঘর্ষ-যাচাই

---

*"Mission Control is the operator experience, not the owner of the private intelligence."*
— roadmap §9; এই প্রোব সেটিই প্রমাণ করে লিপিবদ্ধ করল।
