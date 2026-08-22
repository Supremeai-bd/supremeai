# 🎨 SupremeAI Dashboard & Design System Master Plan

**Document Version:** 3.0.0 (Canonical Source of Truth)  
**System Phase:** **Phase 3: Self-Evolving & Multi-Agent Swarm**  
**Classification:** Frontend Design System, UI/UX Architecture & Shared Shell

---

## 🎯 1. Design Aesthetics & Visual Identity

SupremeAI একটি প্রিমিয়াম **Dark-Neon Aesthetic** অনুসরণ করে। এটি সাধারণ হালকা বা একঘেয়ে ড্যাশবোর্ড নয়; বরং একটি হাই-টেক, লাইভ এবং অত্যন্ত রেসপনসিভ এন্টারপ্রাইজ কন্ট্রোল সেন্টার।

- **Background:** Dense Dark-Neon (`#09090b` / `slate-950`), Aurora vignette overlay.
- **Accents:** 
  - **Admin (God Mode):** Cyber Cyan (`#00F3FF`, glow: `rgba(0, 243, 255, 0.35)`)
  - **Operator (User):** Hyper Purple (`#A855F7`, glow: `rgba(168, 85, 247, 0.35)`)
- **Typography:** `Plus Jakarta Sans` / `Inter` (UI), `JetBrains Mono` (Code/Metrics), `tabular-nums` (KPI metrics).
- **Surfaces:** Glassmorphic translucent cards (`bg-slate-900/60 backdrop-blur-md border-white/5`).

---

## 🏛️ 2. Information Architecture (Shared Shell)

একটি একক ইউনিফাইড শেলের মধ্যে রোল-বেসড সুইচিং (`[ User | Admin ]` pills) পরিচালিত হয়:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ HEADER: [☰ Toggle] SupremeAI ◉   [Search ⌘K]   [User | Admin]   [🔔]  [Avatar]│
├──────────────┬──────────────────────────────────────────────────────────────┤
│ SIDEBAR      │  MAIN VIEWPORT (Overflow-Y Auto)                             │
│ ┌──────────┐ │  Breadcrumb: Workspace > Agent Studio                        │
│ │Workspace │ │  Page Header: Eyebrow + H1 Title + Subtitle                  │
│ │• Agent   │ │                                                              │
│ │• IDE     │ │  KPI Row: [StatCard 1] [StatCard 2] [StatCard 3]             │
│ │• Swarm   │ │                                                              │
│ ├──────────┤ │  Dynamic Canvas / Terminal / Chat / Living Dashboard Grid   │
│ │Discover  │ │  • Swarm Map Telemetry                                       │
│ │• Skills  │ │  • Evolution Forge & Skill Graph                             │
│ │• Tower   │ │  • Live Event Stream & Health Map                            │
│ └──────────┘ │                                                              │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

---

## 🧱 3. Reusable UI Primitives (`frontend/src/components/ui/`)

1. **`StatCard.tsx`:** ছোট uppercase লেবেল, বড় **tabular-nums** মেট্রিক ভ্যালু এবং ডেল্টা ট্রেন্ড টোন (positive/negative/neutral)।
2. **`Breadcrumb.tsx`:** মাল্টি-লেভেল নেভিগেশন ডেপথ ও অ্যাক্সেসিবিলিটি ওরিয়েন্টেশন (`aria-current="page"` সহ)।
3. **`PageHeader.tsx`:** কাস্টম আইব্রো, ডায়নামিক H1 হেডিং এবং অ্যাকশন বাটন সহ পেজ হিরো কম্পোনেন্ট।
4. **`NavRail.tsx`:** গ্রুপড নেভিগেশন (Workspace / Discover), স্মার্ট হোভার/পিন এক্সপ্যান্ড এবং কোলাপস কন্ট্রোল।
5. **`CommandBar.tsx`:** ইউনিভার্সাল কমান্ড প্যালেট (`Ctrl+K` / `⌘K`) — ডাটা-ড্রাইভেন রাউটিং, এআই অ্যাকশন এবং মডেল সুইচার।

---

## 🌐 4. Unified Shared Shell & Role Switching

- **Zero-Split Build:** আলাদা `dist-admin` এবং `dist-user` ডিপ্লয়মেন্ট ম্যানেজমেন্টের ঝামেলা দূর করে একক বিল্ডে রোল-গার্ডেড রাউটিং।
- **Dynamic Pills:** হেডারের রোল সুইচারে ক্লিক করলেই পার্পল (User `/workspace`) এবং সায়ান (Admin `/admin`) মোডে মসৃণ ট্রানজিশন।

---
*Canonical Master Plan — Supersedes all legacy dashboard and frontend planning drafts.*
