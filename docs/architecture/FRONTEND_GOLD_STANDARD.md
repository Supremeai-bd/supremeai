# 🎨 Frontend Gold Standard Blueprint: Simple for Everyone, Powerful on Demand

**Version:** 4.0 (Master Frontend Architecture & Technical Implementation Contract)  
**Core Law:** **"Never forcefully dump everything on everyone. The UI is Task-First, not Panel-First. The Server is the source of truth; the user decides their preferred language, feature guidance level, and workspace immersion."**  
**Guiding Formula:**  
> **Panel-first UI নয় — Task-first UI;**  
> **localStorage-first নয় — Server-synced preference;**  
> **Jargon-heavy UI নয় — Universal language + Interactive feature hints;**  
> **Visual layout test নয় — Real user outcome measurement।**

---

## ১. ভূমিকা ও কোর দর্শন (Core Philosophy: No Forced Complexity)

SupremeAI ব্যাকএন্ড অত্যন্ত শক্তিশালী (Autonomous Agent Swarm, Terminal Sandbox, WebContainer, MCP Tools, Playwright Browser, Vector Memory, Multi-Tenant Isolation)। কিন্তু:

> **"সবার জন্য সব ফিচার জোর করে স্ক্রিনে ফেলে দেওয়া (Forced Dumping) একটি মারাত্মক ইউজার এক্সপেরিয়েন্স অ্যান্টি-প্যাটার্ন।"**

### ইউজারের বিভিন্ন ধরন ও চাহিদা (User Personas):
1. **General User (Ask & Learn):** তার প্রয়োজন **শুধুমাত্র একটি পরিষ্কার, সুন্দর এবং স্মার্ট Chat Interface**। কোনো কোড এডিটর, টার্মিনাল বা ক্লাউড লগ দেখার প্রয়োজন নেই।
2. **Researcher (Research & Surfing):** তার প্রয়োজন **Chat + Automatic Browser Preview** (এজেন্ট যখন ইন্টারনেট সার্ফ বা ডেটা এক্সট্রাক্ট করবে, তখন ব্রাউজার লাইভ দেখা যাবে)।
3. **Creator (Content & Documents):** তার প্রয়োজন **Chat + Document / Draft Viewer** (নোট, আর্টিকেল বা সামারি লাইভ দেখার জন্য)।
4. **Builder / Developer (Build):** তার প্রয়োজন **Chat + Code Editor + Terminal + Live Hot-Reload Preview**।

---

## ২. মেজারেবল ইউএক্স গোলস ও পারফরম্যান্স বাজেট (Measurable UX Goals & Performance Budget)

"১০০% ইউজার-ফ্রেন্ডলি" কোনো ইঞ্জিনিয়ারিং মেট্রিক নয়। সুনির্দিষ্ট ও পরিমাপযোগ্য গোলস:

### ক. ইউজার এক্সপেরিয়েন্স বেঞ্চমার্ক (UX Metrics):
1. **Time to First Action:** নতুন ইউজার সাইন-আপ করার **৬০ সেকেন্ডের মধ্যে** কোনো নির্দেশিকা বা টিউটোরিয়াল না পড়েই প্রথম টাস্ক শুরু করতে পারবে।
2. **Task Efficiency:** সাধারণ বা কোর কাজগুলো **৩ থেকে ৫টি ইন্টারঅ্যাকশন স্টেপের মধ্যে** সম্পন্ন হতে হবে।
3. **Cognitive Clarity:** স্ক্রিনের যেকোনো মুহূর্তে ইউজার স্পষ্টভাবে বুঝতে পারবে: **"এখন কী হচ্ছে?"** এবং **"এখন আমার কী করণীয়?"**।
4. **Error Recovery Rate:** ব্যর্থ কাজ থেকে ইউজারের সফল রিকভারি রেট **> ৯৫%** হতে হবে (কখনো কোনো ডেটা হারাবে না)।
5. **Usability Testing Benchmark:** প্রথমবার ব্যবহারকারী নন-টেকনিক্যাল ইউজারদের মধ্যে **৮৫–৯০%** কোনো মানুষের সাহায্য ছাড়া নির্ধারিত কাজ সফলভাবে শেষ করতে পারবে।
6. **Feature Discovery & Understanding:** নতুন ফিচারগুলো ইউজারের নিজের ভাষায় তৈরি সহজ হিন্টসের মাধ্যমে **> ৮০% ইউজার** প্রথমবার দেখেই এর উদ্দেশ্য বুঝতে পারবে।

### খ. কোর ওয়েব ভাইটালস ও পারফরম্যান্স বাজেট (Core Web Vitals Budget):
| মেট্রিক | টার্গেট সীমা | কারিগরি যৌক্তিকতা |
|---|---|---|
| **LCP (Largest Contentful Paint)** | `< 2.5s` | প্রধান কনটেন্টের দ্রুত ডিসপ্লে |
| **INP (Interaction to Next Paint)** | `< 200ms` | মসৃণ ও তাৎক্ষণিক রেসপন্সিভনেস |
| **CLS (Cumulative Layout Shift)** | `< 0.1` | কোনো ধরনের লেআউট জাম্প বা ঝাঁকুনি নেই |
| **FCP (First Contentful Paint)** | `< 1.8s` | প্রথম স্ক্রিন লোডের গতি |
| **Initial Bundle Size** | `< 300KB (gzipped)` | ফ্রি-টিয়ার হোস্টিং ব্যান্ডউইথ সাশ্রয়ী |
| **TTI (Time to Interactive)** | `< 3.5s` | পূর্ণ ইন্টারেক্টিভ হওয়ার সময় |
| **Browser Console State** | **০ লাল এরর / ০ হলুদ ওয়ার্নিং** | ১০০% ক্লিন ও বাগমুক্ত প্রোডাকশন কোড |

---

## ৩. ইউনিভার্সাল ভাষা ও ক্যানোনিকাল i18n সিস্টেম (Universal Language & i18n Strategy)

### ক. তিনটি প্যারালাল i18n সিস্টেম কনসোলিডেশন (i18n Consolidation Mandate):
কোডবেসে পূর্বে ৩টি ভিন্ন i18n ট্র্যাক থাকায় ফ্র্যাগমেন্টেশন তৈরি হচ্ছিল:
1. `useTranslation.ts`
2. `i18n/useI18n.ts` + `I18nProvider.tsx`
3. অব্যবহৃত `react-i18next` ও `i18next` ডিপেন্ডেন্সি

**গোল্ড স্ট্যান্ডার্ড একক সিদ্ধান্ত:**
- **ক্যানোনিকাল সিস্টেম:** কাস্টম জিরো-ডিপেন্ডেন্সি `useTranslation` হুক (Zero bundle overhead, সম্পূর্ণ টাইপসেফ, বাংলা/বাংলিশ পূর্ণ নিয়ন্ত্রণ)।
- **ডিপেন্ডেন্সি রিমুভাল:** `react-i18next`, `i18next`, এবং ডুপ্লিকেট `i18n/useI18n.ts` সম্পূর্ণরূপে বাদ দেওয়া হবে (Bundle size হ্রাস)।

### খ. সেটিংস-এ ভাষা নির্বাচন ও ডুয়েল সিঙ্ক (Language Selector & AI Sync):
- ইউজার তার সুবিধামতো যেকোনো ভাষা বাছাই করতে পারবে (**সহজ বাংলা**, **English**, **Spanish**, **Hindi**, **Banglish**)।
- **UI Localization:** সম্পূর্ণ ইউআই, নেভিগেশন, স্ট্যাটাস মেসেজ এবং বাটন ওই ভাষায় অনুদিত হবে।
- **Default AI Conversation Language:** এজেন্ট চ্যাটের ডিফল্ট ভাষা হিসেবে এটি সরাসরি ব্যবহার করবে। ইউজার যে ভাষায়ই লিখুক না কেন, এজেন্ট ইউজারের সিলেক্ট করা ভাষার স্বাচ্ছন্দ্যে উত্তর দেবে।
- ভাষা পছন্দটি সার্ভারে ইউজারের প্রোফাইলে সেভ থাকবে এবং সব ডিভাইসে সিঙ্ক হবে।

### গ. ইন্টারেক্টিভ ফিচার গাইডেন্স ও স্মার্ট হিন্টস (Smart Feature Hints System):
প্রতিটি ফিচারের সাথে হালকা একটি `[?]` বা হোভার/ক্লিক হিন্ট আইকন থাকবে যা ইউজারের নির্বাচিত ভাষায় ৩টি প্রশ্নের উত্তর দেবে:
1. **💡 ফিচারটি কী? (What is it?):** সহজ ১ লাইনের পরিচিতি।
2. **⚙️ এটি কীভাবে কাজ করে? (How does it work?):** ব্যাকএন্ডের জটিলতা ছাড়া এর কাজের সারমর্ম।
3. **🚀 কীভাবে ব্যবহার করবেন? (How to use it?):** বাস্তব উদাহরণসহ ব্যবহারের নিয়ম।

---

## ৪. ফ্রন্টএন্ড স্টেট ম্যানেজমেন্ট আর্কিটেকচার (State Layer Contract)

ফ্রন্টএন্ডের সমস্ত স্টেট পরিষ্কার তিনটি স্তরে বিন্যস্ত থাকবে (কোনো ডুপ্লিকেট স্টেট রাখা যাবে না):

```
┌─────────────────────────────────────────────────────────────┐
│                 ZUSTAND (Client UI State)                   │
│   • active panels, workspace layout, theme, modal states    │
│   • thin client authentication tokens                       │
├─────────────────────────────────────────────────────────────┤
│             @TANSTACK/REACT-QUERY (Server State)            │
│   • /api/v1/user/preferences (synced layout & language)     │
│   • agent task execution status, HITL approvals             │
│   • query caching, optimistic updates, auto-retry           │
├─────────────────────────────────────────────────────────────┤
│                 DEXIE / INDEXEDDB (Local First)             │
│   • offline draft persistence (typing never lost)           │
│   • local chat history archive, large artifact cache        │
└─────────────────────────────────────────────────────────────┘
```

---

## ৫. রিয়েল-টাইম স্ট্রিমিং আর্কিটেকচার (Streaming & Real-Time Protocol)

এআই রেসপন্স প্রদর্শনের জন্য সার্ভার-সেন্ট ইভেন্টস (SSE) স্ট্যান্ডার্ড প্রোটোকল:

1. **রিয়েল-টাইম টোকেন স্ট্রিমিং:**
   - চ্যাট উত্তরগুলো SSE কানেকশন দিয়ে লাইভ স্ট্রিম হবে।
   - প্রগ্রেসিভ মার্কডাউন পার্সার আংশিক টোকেন রেন্ডার করার সময় কোড ব্লক ভাঙবে না।
2. **স্ট্রিমিং ক্যান্সেলেশন (Stop & Keep Draft):**
   - ইউজার যেকোনো মুহূর্তে `[Stop]` চাপলে সাথে সাথে ব্যাকএন্ড জেনারেশন বাতিল করবে এবং ততক্ষণে তৈরি হওয়া আংশিক রেসপন্স সংরক্ষিত থাকবে।
3. **অটো-রিকানেক্ট ও ইভেন্ট ট্র্যাকিং:**
   - নেটওয়ার্ক ড্রপ হলে `Last-Event-ID` দিয়ে স্বয়ংক্রিয়ভাবে রিকানেক্ট হবে, কোনো টোকেন ড্রপ হবে না।
4. **কানেকশন হেলথ ইন্ডিকেটর:**
   - স্ক্রিনে একটি হালকা স্ট্যাটাস ডট (সবুজ = সংযুক্ত, হলুদ = রিকানেক্ট হচ্ছে, লাল = অফলাইন) থাকবে।

---

## ৬. টাস্ক-ফার্স্ট আর্কিটেকচার ও প্রেসেট ট্যাক্সোনমি (Task-First Architecture)

ইউজার আগে প্যানেল বা লেআউট বাছাই করতে বাধ্য হবে না। ইউজার তার সমস্যার কথা বলবে—সিস্টেম স্বয়ংক্রিয়ভাবে তার প্রয়োজনীয় ওয়ার্কস্পেস সাজেশন দেবে:

```
User describes task
        ↓
SupremeAI detects needed intent/workspace
        ↓
Shows gentle suggestion ("আপনি ওয়েবসাইট বানাচ্ছেন। Build Workspace অন করব? [অন করুন] [চ্যাটেই থাকুন]")
        ↓
User approves or ignores (Zero forced screen jumping)
```

### সহজ ও টাস্ক-ভিত্তিক প্রিসেট নেমিং (Human-Centered Presets):
| প্রিসেট নাম | টার্গেট অ্যাক্টিভিটি | ডিফল্ট সক্রিয় প্যানেল |
|---|---|---|
| **💬 Ask and Learn** | প্রশ্ন-উত্তর, চ্যাট, ব্রেনস্টর্মিং | শুধু সেন্ট্রাল ক্লিন চ্যাট |
| **🌐 Research** | ওয়েব স্ক্র্যাপিং, তথ্য অনুসন্ধান | চ্যাট + অটোমেটিক লাইভ ব্রাউজার |
| **📝 Create** | আর্টিকেল, রিপোর্ট, ডকুমেন্ট লেখা | চ্যাট + ক্লিন ডকুমেন্ট ভিউয়ার |
| **🛠️ Build** | ওয়েবসাইট, সফটওয়্যার, অ্যাপ তৈরি | চ্যাট + কোড এডিটর + লাইভ প্রিভিউ (+ টার্মিনাল অন ডিমান্ড) |
| **🎨 Custom** | ইউজারের নিজস্ব পারসোনালাইজড লেআউট | ইউজারের নিজের সাজানো কম্বিনেশন |

*(নোট: জটিল নাম "Studio" বা "Developer Mode" শুধু Advanced Settings এর ভেতরে থাকবে; মূল ইন্টারফেসে থাকবে সহজ "Build" বা "Research")*

---

## ৭. সার্ভার-সিঙ্কড প্রেফারেন্স মডেল (TypeScript Contract)

`localStorage` কোনো অবস্থাতেই Primary Source of Truth হতে পারবে না। এটি শুধুমাত্র অফলাইন ফলব্যাক ও ইনস্ট্যান্ট অপটিমিস্টিক ক্যাশ হিসেবে কাজ করবে।

### ফ্রন্টএন্ড কনজাম্পশন টাইপ ইন্টারফেস (Frontend TypeScript Contract):
```typescript
export interface UserWorkspacePreferences {
  user_id: string;
  tenant_id: string;
  workspace_id: string;
  preferred_language: 'bn' | 'en' | 'es' | 'hi' | 'banglish';
  ai_personality: 'concise' | 'friendly' | 'professional' | 'architect';
  response_speed: 'lightning' | 'deep_thinker';
  feature_hints_level: 'all' | 'minimal' | 'none';
  theme: 'dark_neon' | 'midnight_oled' | 'soft_light' | 'high_contrast';
  font_size: 'normal' | 'medium' | 'large';
  bangla_font: 'solaiman_lipi' | 'hind_siliguri' | 'noto_sans';
  reduce_motion: boolean;
  browser_approval_strictness: 'strict' | 'balanced';
  auto_wipe_session: boolean;
  sound_effects: boolean;
  text_to_speech_auto: boolean;
  selected_mode: 'ask_and_learn' | 'research' | 'create' | 'build' | 'custom';
  active_panels: {
    chat: boolean;
    browser: boolean;
    editor: boolean;
    terminal: boolean;
    document: boolean;
  };
  panel_sizes: Record<string, string>;
  panel_order: string[];
  updated_at: string;
}
```

### পূর্ণাঙ্গ সেটিংস হাব (Settings Hub Categories):
1. **AI Personality & Tone:** Concise, Friendly, Professional, Architect
2. **Speed vs Thinking:** Lightning চ্যাট বনাম Deep Thinker
3. **Feature Hints Level:** All Hints, Minimal, None
4. **Theme & Typography:** Dark Neon, Midnight OLED, Soft Light, বাংলা ফন্ট (SolaimanLipi / Hind Siliguri)
5. **Privacy & Security:** Strict/Balanced Browser HITL, Auto-Wipe Session Cookies
6. **Sound & Accessibility:** UI Sound Effects, Auto TTS, Reduce Motion
7. **Shortcuts & Sync:** Custom Hotkeys (`Ctrl+K`, `Ctrl+\`), 1-Click Multi-Device Sync

---

## ৮. রেসপনসিভ ভিউপোর্ট রুলস (Strict Responsive Viewport Engine)

সাধারণ CSS Grid দিয়ে পাশাপাশি ৫০/৫০ ভাগ করলে মোবাইল বা ট্যাবলেটে ইন্টারফেস ভেঙে যায়। তাই কঠোর ডিভাইস নিয়ম এনফোর্স করা হবে:

| ডিভাইস সাইজ | ভিউপোর্ট প্রস্থ | সর্বোচ্চ সক্রিয় প্যানেল | লেআউট আচরণ |
|---|---|---|---|
| **Mobile** | `< 768px` | **১টি** (একবারে শুধু একটি প্যানেল) | অন্য প্যানেলগুলো Bottom Sheet অথবা Swipeable Tab আকারে আসবে। কোনো অবস্থাতেই পাশাপাশি স্প্লিট হবে না। |
| **Tablet** | `768px – 1024px` | **সর্বোচ্চ ২টি** | চ্যাট + ১টি আউটপুট প্যানেল। টার্মিনাল ও এডিটর কখনোই একসাথে পাশাপাশি বসবে না। |
| **Desktop** | `> 1024px` | **২ থেকে ৩টি** | অ্যাডাপ্টিভ স্প্লিট ভিউ (চ্যাট + রেজাল্ট + অপশনাল টার্মিনাল ড্রয়ার)। |

---

## ৯. সিকিউরিটি: আউটপুট স্যানিটাইজেশন ও XSS প্রিভেনশন (Content Security)

SupremeAI এআই-জেনারেটেড HTML, Markdown এবং Code রেন্ডার করে। তাই নিরাপত্তা সুনিশ্চিত করতে হবে:

1. **DOMPurify স্যানিটাইজেশন:**
   - ইউজারের দেওয়া টেক্সট বা এআই থেকে আসা কোনো HTML সরাসরি রেন্ডার করা নিষিদ্ধ। সমস্ত কন্টেন্ট বাধ্যতামূলকভাবে `DOMPurify.sanitize()` এর মাধ্যমে ফিল্টার হবে।
2. **স্যান্ডবক্সড আইফ্রেম (Strict Iframe Sandbox):**
   - Monaco Editor বা লাইভ কোড প্রিভিউ অবশ্যই স্যান্ডবক্সড আইফ্রেমে চলবে (`sandbox="allow-scripts"` থাকবে, কিন্তু `allow-same-origin` সম্পূর্ণ নিষিদ্ধ)।
3. **Zero dangerouslySetInnerHTML:**
   - কোডবেসে কোনো অপরীক্ষিত `dangerouslySetInnerHTML` থাকবে না।

---

## ১০. লেয়ার্ড এরর বাউন্ডারি ও ফল্ট টলারেন্স (Error Boundary Layering)

কোডবেসের ডুপ্লিকেট এরর বাউন্ডারি কনসোলিডেট করে ৩টি সুনির্দিষ্ট স্তর থাকবে:

```
┌─────────────────────────────────────────────────────────────┐
│ L1: GlobalErrorBoundary (App Root Crash Protection)        │
│   • অ্যাপ ক্র্যাশ করলে ফ্রেন্ডলি স্ক্রিন ও ১-ক্লিক রিলোড    │
├─────────────────────────────────────────────────────────────┤
│ L2: Panel-Level Boundaries (Isolated Panel Faults)          │
│   • ব্রাউজার বা এডিটর ক্র্যাশ করলেও চ্যাট সম্পূর্ণ অক্ষত থাকবে│
├─────────────────────────────────────────────────────────────┤
│ L3: Component-Level Graceful Degradation                   │
│   • স্কেলেটন লোডার → ফ্রেন্ডলি এরর মেসেজ → অটো রিট্রাই বাটন │
└─────────────────────────────────────────────────────────────┘
```

---

## ১১. নোটিফিকেশন ও গ্লোবাল কমান্ড প্যালেট (Toasts & Command Bar)

1. **কমান্ড প্যালেট (`Ctrl+K`):**
   - সম্পূর্ণ প্ল্যাটফর্মে একটাই গ্লোবাল কমান্ড প্যালেট।
   - ফাজি সার্চ (Fuzzy search), রিসেন্ট হিস্ট্রি এবং কিবোর্ড দিয়ে ১-ক্লিকে যেকোনো সেটিংস বা ওয়ার্কস্পেসে সুইচ করা।
2. **নোটিফিকেশন সেন্টার ও টোস্ট সিস্টেম:**
   - ব্যাকগ্রাউন্ড টাস্ক শেষ হলে হালকা টোস্ট মেসেজ।
   - HITL এপ্রুভাল পেন্ডিং থাকলে হেডারে নোটিফিকেশন ব্যাজ।

---

## ১২. ব্রাউজার অটোমেশন প্রাইভেসি ও এপ্রুভাল গেটওয়েল (HITL for Browser)

যখন এজেন্ট লাইভ ব্রাউজার ব্যবহার করে ওয়েব সার্ফ করবে:
1. **ভিজ্যুয়াল সচেতনতা (Visible Transparency):** কোন URL ভিজিট করছে তা স্পষ্টভাবে অ্যাড্রেস বারে প্রদর্শন।
2. **হিউম্যান-ইন-দ্য-লুপ এপ্রুভাল (HITL Guardrails):** কোনো সাইটে **Login**, **Password Input**, **Payment/Checkout** বা **Form Submit** করার আগে পপ-আপে ইউজারের সুস্পষ্ট অনুমোদন চাইতে হবে।
3. **সেশন ক্লিনআপ (Session Hygiene):** ব্রাউজার প্যানেল বন্ধ করলে বা সেশন শেষ হলে কুকি, স্যান্ডবক্স ক্যাশ ও সাময়িক অথেন্টিকেশন স্টেট স্বয়ংক্রিয়ভাবে ধ্বংস (Wipe) হয়ে যাবে।

---

## ১৩. সম্পূর্ণ স্ট্যাটাস কপি ও হিউম্যান-ফ্রেন্ডলি ডিকশনারি (Status States & Recovery)

### কাজের প্রতিটি ধাপের রিয়েল-টাইম স্ট্যাটাস স্টেজ (দ্বৈত ভাষায় সমর্থিত):
| স্ট্যাটাস স্টেট | ইন্টারনাল স্টেট | ইংরেজি কপি | সহজ বাংলা কপি | ইউজার অ্যাকশন ও রিকভারি |
|---|---|---|---|---|
| **Idle** | `IDLE` | "Ready for your next request" | "পরবর্তী নির্দেশনার জন্য প্রস্তুত" | ইনপুট প্রম্পট দিন |
| **Understanding** | `PARSING` | "Understanding what you need..." | "আপনার নির্দেশটি বোঝা হচ্ছে..." | `[Cancel]` |
| **Waiting Approval** | `HITL_PENDING` | "SupremeAI needs your permission" | "সামনে অগ্রসর হতে আপনার অনুমতি প্রয়োজন" | `[অনুমোদন দিন]` / `[বাতিল]` |
| **Working** | `EXECUTING` | "Crafting your first draft..." | "খসড়া তৈরি করা হচ্ছে..." | `[থামান ও খসড়া রাখুন]` |
| **Needs Info** | `AMBIGUOUS` | "A quick question to get this right..." | "সঠিক করার জন্য একটি ছোট্ট প্রশ্ন..." | অপশন বেছে নিন |
| **Completed** | `SUCCESS` | "All done! Here is your result." | "সম্পন্ন হয়েছে! আপনার ফলাফল প্রস্তুত।" | `[পূর্বের অবস্থায় ফিরুন]` / `[শেয়ার]` |
| **Partially Completed** | `PARTIAL` | "Completed 3 of 4 steps." | "৪টির মধ্যে ৩টি ধাপ সম্পন্ন হয়েছে।" | `[বাকিটুকু চালান]` / `[ডাউনলোড]` |
| **Failed Recoverable** | `ERROR_RETRY` | "Preview couldn't load, code is safe." | "প্রিভিউ আসেনি, তবে আপনার কাজ নিরাপদ আছে।" | `[পুনরায় চেষ্টা করুন]` |
| **Failed Escalated** | `ERROR_HALT` | "Something unexpected happened." | "একটি অনাকাঙ্ক্ষিত সমস্যা হয়েছে।" | `[আগের খসড়া পুনরুদ্ধার করুন]` |
| **Cancelled** | `ABORTED` | "Task stopped. Restored previous state." | "কাজ থামানো হয়েছে। পূর্বের অবস্থা সংরক্ষিত।" | `[আবার শুরু করুন]` |

---

## ১৪. বিস্তৃত টেস্টিং স্ট্র্যাটেজি ও ডেফিনিশন অফ ডান (Testing & DoD)

| ক্যাটাগরি | মেট্রিক ও যাচাইকরণ পদ্ধতি | মানদণ্ড |
|---|---|---|
| **Accessibility (A11y)** | axe-core, WCAG 2.1 AA | সঠিক ARIA রোলস, কন্টাক্ট রেশিও > 4.5:1 |
| **Keyboard Navigation** | সম্পূর্ণ ওয়ার্কস্পেস শুধু কিবোর্ডে | `Tab`, `Ctrl+K`, `Esc`, `Arrow Keys` ১০০% কার্যকর |
| **Multi-Language UI** | বাংলা, ইংরেজি ও বাংলিশ সুইচিং | কোনো টেক্সট ওভারফ্লো নেই, নিখুঁত টাইপোগ্রাফি |
| **Mobile Viewport** | Chrome DevTools ও বাস্তব ডিভাইসে | `<768px` এ সিঙ্গেল প্যানেল, টাচ টার্গেট > 44px |
| **Resilience & Offline** | স্লো নেটওয়ার্ক ও ব্যাকএন্ড ফল্ট টেস্ট | টাইপ করা ড্রাফট নষ্ট হবে না, অটো রিকভারি > ৯৫% |
| **E2E Visual Regression** | Playwright E2E টেস্ট স্যুট | বিভিন্ন রেজোলিউশনে স্ক্রিনশট ম্যাচিং ও ফ্লো টেস্ট |
| **Browser Console** | হেডলেস ব্রাউজার কনসোল লিসেনার | **০ লাল এরর / ০ হলুদ ওয়ার্নিং** |
| **PWA Readiness** | Manifest & Service Worker | অফলাইন ক্যাশিং ও সঠিক আইকন অ্যাসেটস |

---

## ১৫. সংশোধিত বাস্তবায়ন রোডম্যাপ (Implementation Roadmap)

```
১. i18n কনসোলিডেশন (একক useTranslation রাখা ও অপ্রয়োজনীয় প্যাকেজ ছাঁটাই)
   ↓
২. ফ্রন্টএন্ড স্টেট লেয়ার কন্ট্রাক্ট (Zustand + React Query + Dexie)
   ↓
৩. রিয়েল-টাইম SSE স্ট্রিমিং ও স্ট্রিমিং ক্যান্সেলেশন প্রোটোকল
   ↓
৪. সার্ভার-সিঙ্কড প্রেফারেন্স এপিআই সংযোগ (/api/v1/user/preferences)
   ↓
৫. Clean Chat Home Screen (Ask and Learn) ডিফল্ট হিসেবে স্থাপন
   ↓
৬. ৩-স্তরের এরর বাউন্ডারি (Global, Panel, Component) কনসোলিডেশন
   ↓
৭. Adaptive Workspace Shell ও মোবাইল-ফার্স্ট ভিউপোর্ট রুলস প্রয়োগ
   ↓
৮. টাস্ক-ভিত্তিক প্রিসেট (Research, Create, Build) ও স্মার্ট সাজেশন যুক্ত করা
   ↓
৯. DOMPurify ও আইফ্রেম স্যান্ডবক্সিং দিয়ে আউটপুট সিকিউরিটি এনফোর্স করা
   ↓
১০. সেটিংস হাব ও ৩-ধাপের ইন্টারেক্টিভ ফিচার গাইডেন্স (স্মার্ট হিন্টস) যোগ করা
   ↓
১১. Full E2E & Usability Testing সম্পন্ন করে প্রোডাকশনে রিলিজ করা
```
