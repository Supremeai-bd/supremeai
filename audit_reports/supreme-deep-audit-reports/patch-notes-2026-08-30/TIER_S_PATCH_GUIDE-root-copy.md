# SupremeAI Tier-S ফিচার প্যাচ — সম্পূর্ণ গাইড

## ওভারভিউ

SupremeAI-তে ১২টি নতুন Tier-S ফিচার যোগ করার জন্য ফুল প্যাচ তৈরি করা হয়েছে। এই ফিচারগুলো চ্যাট অভিজ্ঞতাকে উল্লেখযোগ্যভাবে উন্নত করবে — conversation sharing থেকে শুরু করে deep research পর্যন্ত।

### Tier-S ফিচার তালিকা

| ID | ফিচার নাম | বিবরণ |
|----|-----------|------|
| S1 | Public Share Links | Conversation শেয়ার করার জন্য public link তৈরি |
| S2 | Reasoning/Thinking Display | Tree-of-Thought ও Debate engine-এর reasoning steps দেখানো |
| S3 | Artifacts Panel | চ্যাট থেকে HTML/React/SVG/Mermaid artifacts তৈরি ও প্রদর্শন |
| S4 | Image Upload | চ্যাটে ছবি আপলোড ও attachment হিসেবে পাঠানো |
| S5 | Slash Commands | `/` টাইপ করে দ্রুত কমান্ড অ্যাক্সেস |
| S6 | Chat Search | `Cmd+K` দিয়ে সব চ্যাট মেসেজ সার্চ |
| S7 | Chat Export | Markdown, JSON, PDF ফরম্যাটে conversation export |
| S8 | Global Memory | ক্রস-conversation context memory সংরক্ষণ ও ব্যবহার |
| S9 | Prompt Library | Reusable prompt templates তৈরি, সেভ ও ব্যবহার |
| S10 | Scheduled Tasks | নির্দিষ্ট সময়ে বা cron schedule-এ চ্যাট প্রম্পট auto-execute |
| S11 | Conversation Branching | যেকোনো মেসেজ থেকে নতুন conversation branch তৈরি |
| S12 | Deep Research | Multi-step AI-powered research সেশন |

---

## ফাইল তালিকা

### Backend — Route Files (১২টি)

| # | ফাইল পথ | ফিচার | বিবরণ |
|---|----------|--------|--------|
| 1 | `backend/api/routes/share.py` | S1 | Share link generate, view, list, revoke |
| 2 | `backend/api/routes/reasoning.py` | S2 | Reasoning think ও stream endpoints |
| 3 | `backend/api/routes/artifacts.py` | S3 | CRUD operations for artifacts |
| 4 | `backend/api/routes/chat_upload.py` | S4 | Multipart file upload handler |
| 5 | `backend/api/routes/slash_commands.py` | S5 | Slash command definitions list |
| 6 | `backend/api/routes/chat_search.py` | S6 | Full-text chat message search |
| 7 | `backend/api/routes/chat_export.py` | S7 | Export to markdown/json/pdf |
| 8 | `backend/api/routes/global_memory.py` | S8 | Cross-conv memory CRUD |
| 9 | `backend/api/routes/prompt_templates.py` | S9 | Prompt template CRUD + usage tracking |
| 10 | `backend/api/routes/scheduled_tasks.py` | S10 | Task CRUD, manual/automatic run |
| 11 | `backend/api/routes/branch_conversations.py` | S11 | Branch from any message |
| 12 | `backend/api/routes/deep_research.py` | S12 | Research session start/status/report |

### Backend — Infrastructure Files (২টি)

| # | ফাইল পথ | বিবরণ |
|---|----------|--------|
| 1 | `backend/api/routes/tier_s_routes.py` | সব ১২টি router-এর centralized registry + `register_tier_s_routes()` helper + fallback raw SQL DDL |
| 2 | `backend/alembic_migrations/versions/tier_s_features.py` | Alembic migration — ৭টি নতুন table + ২টি column addition |

### Frontend — Component Files (৮টি)

| # | ফাইল পথ | ফিচার | বিবরণ |
|---|----------|--------|--------|
| 1 | `frontend/src/components/share/ShareDialog.tsx` | S1 | Modal dialog — visibility toggle, expiry selector, link copy |
| 2 | `frontend/src/components/reasoning/ThinkingPanel.tsx` | S2 | Collapsible panel — reasoning steps স্টেপ-বাই-স্টেপ দেখায় |
| 3 | `frontend/src/components/artifacts/ArtifactsPanel.tsx` | S3 | Side panel — artifact list, preview, version toggle |
| 4 | `frontend/src/components/chat/ImageUploadButton.tsx` | S4 | Upload button — drag & drop + file picker |
| 5 | `frontend/src/components/export/ExportMenu.tsx` | S7 | Dropdown menu — Markdown/JSON/PDF export options |
| 6 | `frontend/src/components/branch/BranchButton.tsx` | S11 | Git-branch icon button — branch title input + create |
| 7 | `frontend/src/components/commands/SlashCommandMenu.tsx` | S5 | Floating command palette — ফিল্টারযোগ্য কমান্ড লিস্ট |
| 8 | `frontend/src/components/search/ChatSearchDialog.tsx` | S6 | Full-screen search dialog — result preview + jump-to |

### Frontend — Page Files (২টি)

| # | ফাইল পথ | ফিচার | বিবরণ |
|---|----------|--------|--------|
| 1 | `frontend/src/pages/SharedConversationPage.tsx` | S1 | Public shared conversation viewer (authentication ছাড়া) |
| 2 | `frontend/src/pages/PromptTemplatePage.tsx` | S9 | Full-page prompt library — browse, create, edit, delete |

### Frontend — Store & Route Files (২টি)

| # | ফাইল পথ | বিবরণ |
|---|----------|--------|
| 1 | `frontend/src/store/tierSStore.ts` | Zustand store — সব Tier-S UI state management |
| 2 | `frontend/src/routes/tierSRoutes.tsx` | Route definitions + integration guide string |

**মোট ফাইল: ২৬টি** (Backend 14 + Frontend 12)

---

## ইনস্টলেশন ধাপ

### ধাপ ১: Database Migration

প্রথমে database-এ নতুন tables তৈরি করতে হবে। দুটি উপায় আছে:

**উপায় A — Alembic দিয়ে (Recommended):**

```bash
cd backend
alembic upgrade head
```

এটি `tier_s_features.py` migration রান করবে যা নিচের tables তৈরি করবে:
- `shared_conversations`
- `artifacts`
- `chat_attachments`
- `prompt_templates`
- `scheduled_tasks`
- `scheduled_task_executions`
- `research_sessions`

এবং নিচের existing tables-এ নতুন column যোগ করবে:
- `conversations.parent_conversation_id` (UUID, FK → conversations.id)
- `messages.parent_message_id` (UUID, FK → messages.id)

**উপায় B — Raw SQL (Alembic না থাকলে):**

`tier_s_routes.py` ফাইলে `TIER_S_TABLES_SQL` constant-এ সব DDL আছে। সেটি ব্যবহার করুন:

```python
from api.routes.tier_s_routes import TIER_S_TABLES_SQL
# Execute TIER_S_TABLES_SQL against your PostgreSQL database
```

### ধাপ ২: Backend Router Registration

`backend/api/routers.py` ফাইলে `ALL_ROUTERS` list-এ একটি মাত্র entry যোগ করুন:

```python
ALL_ROUTERS = [
    # ... existing entries ...

    # ── Tier-S (all 12 routers via centralized registry) ──
    {"path": "api.routes.tier_s_routes", "prefix": "", "is_admin": False, "is_critical": False},
]
```

তারপর `backend/api/server.py` ফাইলে (যেখানে routers mount হয়) নিচের কোড যোগ করুন:

```python
from api.routes.tier_s_routes import register_tier_s_routes

# ... existing router registration code ...
register_tier_s_routes(app)
```

এই একটি কলে সব ১২টি router তাদের নির্ধারিত prefix-এ mount হয়ে যাবে।

### ধাপ ৩: NPM Dependencies

Frontend-এ দুটি নতুন package লাগবে PDF export (S7) এবং file download এর জন্য:

```bash
cd frontend
npm install jspdf file-saver
npm install -D @types/file-saver
```

### ধাপ ৪: Frontend Route Integration

`frontend/src/App.tsx` ফাইলে নিচের পরিবর্তনগুলো করুন:

**4a. Import যোগ করুন** (অন্য lazy import-গুলোর সাথে):

```tsx
import { tierSUserRoutes } from './routes/tierSRoutes';
```

**4b. Routes block-ে যোগ করুন** — 404 catch-all route-এর আগে:

```tsx
{/* ═══ Tier-S Feature Routes ═══ */}
{tierSUserRoutes.map((r, i) => (
  <Route key={i} path={r.path!} element={r.element} />
))}

{/* Catch-all 404 Route — এটি সবসময় শেষে থাকবে */}
<Route path="*" element={<ErrorPage code={404} />} />
```

**গুরুত্বপূর্ণ:** `/share/:shareId` route-কে `ProtectedRoute` দিয়ে wrap করবেন না — এটি একটি guest route যাতে যেকেউ শেয়ার লিংক দিয়ে conversation দেখতে পারে।

### ধাপ ৫: Component Integration (ChatInterface.tsx)

`frontend/src/components/chat/ChatInterface.tsx` ফাইলে নিচের পরিবর্তনগুলো করুন:

**5a. Imports যোগ করুন:**

```tsx
import { ShareDialog } from '../share/ShareDialog';
import { ThinkingPanel } from '../reasoning/ThinkingPanel';
import { ArtifactsPanel } from '../artifacts/ArtifactsPanel';
import { ImageUploadButton } from './ImageUploadButton';
import { ExportMenu } from '../export/ExportMenu';
import BranchButton from '../branch/BranchButton';
import { SlashCommandMenu } from '../commands/SlashCommandMenu';
import { ChatSearchDialog } from '../search/ChatSearchDialog';
import { useTierSStore } from '../../store/tierSStore';
```

**5b. Component body-তে store থেকে values নিন:**

```tsx
const {
  shareDialogOpen, shareConversationId, closeShareDialog, openShareDialog,
  showReasoning, reasoningSteps, isThinking,
  artifactsPanelOpen, activeArtifactId, artifacts, selectArtifact, setArtifactsPanelOpen,
  slashMenuOpen, closeSlashMenu, slashFilter, slashPosition, openSlashMenu,
  searchDialogOpen, closeSearchDialog, openSearchDialog,
} = useTierSStore();
```

**5c. Toolbar-এ নতুন buttons যোগ করুন:**

```tsx
{/* S1: Share */}
<button onClick={() => openShareDialog(currentConversationId)} aria-label="Share conversation">
  <Share2 className="w-4 h-4" />
</button>

{/* S7: Export */}
<ExportMenu conversationId={currentConversationId} />

{/* S4: Image Upload */}
<ImageUploadButton
  conversationId={currentConversationId}
  onUploadComplete={(attachment) => { /* handle attachment */ }}
/>
```

**5d. প্রতিটি message bubble-তে BranchButton যোগ করুন (S11):**

```tsx
<BranchButton
  conversationId={currentConversationId}
  messageId={msg.id}
  onBranchCreated={(newConvId) => { navigate(`/workspace?conv=${newConvId}`); }}
/>
```

**5e. Overlay/dialog components render করুন (JSX-এর শেষে):**

```tsx
{/* ═══ Tier-S Overlays ═══ */}
<ShareDialog
  conversationId={shareConversationId || ''}
  isOpen={shareDialogOpen}
  onClose={closeShareDialog}
/>

{showReasoning && <ThinkingPanel steps={reasoningSteps} isThinking={isThinking} />}

{artifactsPanelOpen && (
  <ArtifactsPanel
    artifacts={artifacts}
    activeId={activeArtifactId}
    onSelect={(id) => selectArtifact(id)}
    onClose={() => setArtifactsPanelOpen(false)}
  />
)}

<ChatSearchDialog isOpen={searchDialogOpen} onClose={closeSearchDialog} />

<SlashCommandMenu
  isOpen={slashMenuOpen}
  filter={slashFilter}
  position={slashPosition}
  onSelect={(cmd) => {
    closeSlashMenu();
    setInput((prev) => prev.replace(/\/\S*$/, cmd.insertText || ''));
  }}
  onClose={closeSlashMenu}
/>
```

### ধাপ ৬: Keyboard Shortcut — Cmd+K দিয়ে Search (S6)

`ChatInterface.tsx`-এ একটি `useEffect` যোগ করুন:

```tsx
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      searchDialogOpen ? closeSearchDialog() : openSearchDialog();
    }
  };
  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, [searchDialogOpen, openSearchDialog, closeSearchDialog]);
```

### ধাপ ৭: Slash Command Detection (S5)

Chat input-এর `onChange` handler-এ slash command detection যোগ করুন:

```tsx
const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
  const value = e.target.value;
  setInput(value);

  // Slash command detection — যখন ইউজার "/" টাইপ করে
  const slashMatch = value.match(/(^|\s)\/(\S*)$/);
  if (slashMatch) {
    const rect = e.target.getBoundingClientRect();
    openSlashMenu(slashMatch[2], {
      top: rect.top - 10,
      left: rect.left + 20,
    });
  } else {
    closeSlashMenu();
  }
};
```

Textarea-এ এই handler attach করুন:

```tsx
<textarea
  value={input}
  onChange={handleInputChange}
  placeholder="Type a message… (/ for commands)"
/>
```

---

## প্রতিটি ফিচারের বিস্তারিত

---

### S1: Public Share Links

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/share.py` — Backend route handler
- `frontend/src/components/share/ShareDialog.tsx` — Share link generation dialog
- `frontend/src/pages/SharedConversationPage.tsx` — Public viewer page

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| POST | `/api/share/generate` | নতুন share link তৈরি | ✅
| GET | `/api/share/{share_id}` | Shared conversation দেখুন (public) | ❌
| GET | `/api/share/list` | ইউজারের সব share link-এর তালিকা | ✅
| DELETE | `/api/share/{share_id}` | Share link revoke/delete | ✅

**Frontend Components:**
- `ShareDialog` — Visibility toggle (Public/Private), expiry selector (7d/30d/90d/never), link copy
- `SharedConversationPage` — read-only conversation display, view counter

**কিভাবে টেস্ট করবেন:**
1. যেকোনো conversation খুলুন
2. Share button-এ click করুন
3. Visibility ও expiry সিলেক্ট করে "Generate Share Link" চাপুন
4. লিংক কপি করে নতুন incognito browser-এ ওপেন করুন
5. Conversation read-only mode-এ দেখা যাবে

---

### S2: Reasoning/Thinking Display

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/reasoning.py` — Reasoning engine endpoint
- `frontend/src/components/reasoning/ThinkingPanel.tsx` — Thinking steps panel

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| POST | `/api/reasoning/think` | একবারে সম্পূর্ণ reasoning result | ✅ |
| POST | `/api/reasoning/think/stream` | SSE stream — step-by-step reasoning | ✅ |

Reasoning modes: `quick` (default), `tree_of_thought`, `debate`

**Frontend Components:**
- `ThinkingPanel` — Collapsible panel, প্রতিটি step-এ score ও agent_id দেখায়, loading animation

**কিভাবে টেস্ট করবেন:**
1. চ্যাটে জটিল প্রশ্ন করুন (যেমন: "Explain quantum entanglement step by step")
2. Thinking panel-এ reasoning steps স্ট্রিমিং হতে দেখবেন
3. প্যানেল টগল করে আড়াল করতে/দেখাতে পারবেন

---

### S3: Artifacts Panel

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/artifacts.py` — Artifact CRUD
- `frontend/src/components/artifacts/ArtifactsPanel.tsx` — Side panel

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| GET | `/api/artifacts/` | Conversation-এর সব artifacts | ✅ |
| POST | `/api/artifacts/` | নতুন artifact তৈরি | ✅ |
| GET | `/api/artifacts/{id}` | একটি artifact দেখুন | ✅ |
| PUT | `/api/artifacts/{id}` | Artifact update | ✅ |
| DELETE | `/api/artifacts/{id}` | Artifact মুছুন | ✅ |

Artifact types: `html`, `react`, `svg`, `mermaid`, `code`

**Frontend Components:**
- `ArtifactsPanel` — List view, live preview (HTML/React render), version tracking, pin/unpin

**কিভাবে টেস্ট করবেন:**
1. চ্যাটে code generation রিকোয়েস্ট করুন
2. Artifacts panel-এ generated code দেখা যাবে
3. Preview tab-এ live render দেখুন

---

### S4: Image Upload

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/chat_upload.py` — File upload handler
- `frontend/src/components/chat/ImageUploadButton.tsx` — Upload UI

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| POST | `/api/chat/upload/` | Multipart file upload (max 10MB) | ✅ |

Allowed MIME types: `image/*`, `application/pdf`, `text/*`

**Frontend Components:**
- `ImageUploadButton` — Click-to-upload ও drag-and-drop, progress bar, preview

**কিভাবে টেস্ট করবেন:**
1. Chat input-এর পাশে upload icon দেখবেন
2. Click করে বা drag-and-drop করে ছবি আপলোড করুন
3. Attachment হিসেবে মেসেজের সাথে পাঠানো হবে

---

### S5: Slash Commands

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/slash_commands.py` — Command definitions
- `frontend/src/components/commands/SlashCommandMenu.tsx` — Command palette UI

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| GET | `/api/slash-commands/` | সব উপলব্ধ slash commands | ✅ |

Built-in commands: `/think`, `/research`, `/export`, `/share`, `/branch`, `/clear`, `/help`

**Frontend Components:**
- `SlashCommandMenu` — Floating menu, keyboard navigable, fuzzy filter

**কিভাবে টেস্ট করবেন:**
1. Chat input-এ `/` টাইপ করুন
2. Command menu দেখা যাবে
3. আরো টাইপ করে filter করুন (যেমন `/th`)
4. Arrow keys দিয়ে navigate, Enter দিয়ে select করুন

---

### S6: Chat Search

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/chat_search.py` — Full-text search
- `frontend/src/components/search/ChatSearchDialog.tsx` — Search dialog

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| GET | `/api/chat/search/?q=...&conversation_id=...` | মেসেজ সার্চ | ✅ |

Query params: `q` (search text), `conversation_id` (optional filter), `limit` (default 20)

**Frontend Components:**
- `ChatSearchDialog` — Full-screen dialog, result highlighting, click-to-jump

**কিভাবে টেস্ট করবেন:**
1. `Cmd+K` (Mac) বা `Ctrl+K` (Windows/Linux) চাপুন
2. Search dialog ওপেন হবে
3. কিছু টাইপ করুন — matching messages দেখাবে
4. যেকোনো result-এ click করলে সেই message-এ jump করবে

---

### S7: Chat Export

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/chat_export.py` — Export endpoint
- `frontend/src/components/export/ExportMenu.tsx` — Export dropdown menu

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| GET | `/api/chat/export/{id}/markdown` | Markdown ফরম্যাটে export | ✅ |
| GET | `/api/chat/export/{id}/json` | JSON ফরম্যাটে export | ✅ |
| GET | `/api/chat/export/{id}/pdf` | PDF ফরম্যাটে export | ✅ |

**Frontend Components:**
- `ExportMenu` — Dropdown মেনু, format selection, download trigger
- `jspdf` library PDF generation-এ ব্যবহৃত

**কিভাবে টেস্ট করবেন:**
1. যেকোনো conversation খুলুন
2. Export button (Download icon) এ click করুন
3. Format সিলেক্ট করুন (Markdown/JSON/PDF)
4. ফাইল অটো-ডাউনলোড হবে

---

### S8: Global Memory

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/global_memory.py` — Memory CRUD

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| GET | `/api/global-memory/` | সব saved memories | ✅ |
| POST | `/api/global-memory/` | নতুন memory সেভ | ✅ |
| DELETE | `/api/global-memory/{id}` | Memory মুছুন | ✅ |

Memory context-কে future conversations-এ automatically inject করা হয়।

**কিভাবে টেস্ট করবেন:**
1. API দিয়ে memory save করুন:
   ```bash
   curl -X POST /api/global-memory/ -H "Authorization: Bearer $TOKEN" \
     -d '{"content": "User prefers TypeScript over JavaScript", "source_conversation_id": "..."}'
   ```
2. GET `/api/global-memory/` দিয়ে verify করুন

---

### S9: Prompt Library

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/prompt_templates.py` — Template CRUD
- `frontend/src/pages/PromptTemplatePage.tsx` — Full-page library UI

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| GET | `/api/prompt-templates/` | সব templates (category filter) | ✅ |
| POST | `/api/prompt-templates/` | নতুন template তৈরি | ✅ |
| PUT | `/api/prompt-templates/{id}` | Template update | ✅ |
| DELETE | `/api/prompt-templates/{id}` | Template মুছুন | ✅ |
| POST | `/api/prompt-templates/{id}/use` | Usage count increment | ✅ |

**Frontend Components:**
- `PromptTemplatePage` — Grid/list view, category filter, create/edit modal, one-click use

**কিভাবে টেস্ট করবেন:**
1. `/prompt-library` route-এ যান
2. "Create Template" বাটনে click করুন
3. Name, description, category, prompt text দিন
4. Template সেভ হবে এবং grid-এ দেখাবে
5. যেকোনো template-এ "Use" ক্লিক করলে চ্যাট input-এ prompt ইনসার্ট হবে

---

### S10: Scheduled Tasks

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/scheduled_tasks.py` — Task CRUD + execution

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| GET | `/api/scheduled-tasks/` | সব scheduled tasks | ✅ |
| POST | `/api/scheduled-tasks/` | নতুন task তৈরি | ✅ |
| PUT | `/api/scheduled-tasks/{id}` | Task update | ✅ |
| DELETE | `/api/scheduled-tasks/{id}` | Task মুছুন | ✅ |
| POST | `/api/scheduled-tasks/{id}/run` | Manual trigger | ✅ |

Schedule types: `once`, `daily`, `weekly`, `custom_cron`

**কিভাবে টেস্ট করবেন:**
1. API দিয়ে task তৈরি করুন:
   ```bash
   curl -X POST /api/scheduled-tasks/ -H "Authorization: Bearer $TOKEN" \
     -d '{"title": "Daily summary", "prompt": "Summarize today\'s conversation", "schedule_type": "daily"}'
   ```
2. `POST /api/scheduled-tasks/{id}/run` দিয়ে manual test করুন

---

### S11: Conversation Branching

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/branch_conversations.py` — Branch creation
- `frontend/src/components/branch/BranchButton.tsx` — Branch UI button

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| POST | `/api/branch-conversations/` | Message থেকে branch তৈরি | ✅ |

Request body: `conversation_id`, `message_id`, `branch_title` (optional)

**Frontend Components:**
- `BranchButton` — Git-branch icon, inline title input, loading state

**কিভাবে টেস্ট করবেন:**
1. যেকোনো message bubble-এ hover করুন
2. Branch icon (GitBranch) দেখাবে
3. Click করলে title input আসবে
4. Title দিয়ে Enter চাপুন — নতুন conversation তৈরি হবে সেই message পর্যন্ত

---

### S12: Deep Research

**কি কি ফাইল তৈরি হয়েছে:**
- `backend/api/routes/deep_research.py` — Research session management

**API Endpoints:**

| Method | Path | বিবরণ | Auth
|--------|------|--------|------|
| POST | `/api/deep-research/start` | নতুন research session শুরু | ✅ |
| GET | `/api/deep-research/{id}/status` | Research progress চেক | ✅ |
| GET | `/api/deep-research/{id}/report` | Final report দেখুন | ✅ |

Research stages: `queued` → `searching` → `analyzing` → `synthesizing` → `completed`

**কিভাবে টেস্ট করবেন:**
1. API দিয়ে research শুরু করুন:
   ```bash
   curl -X POST /api/deep-research/start -H "Authorization: Bearer $TOKEN" \
     -d '{"query": "Compare React Server Components vs Astro Islands"}'
   ```
2. `{id}/status` poll করুন — stages পরিবর্তন দেখবেন
3. `completed` হলে `{id}/report` থেকে full report নিন

---

## API Endpoint সারসংক্ষেপ

| Feature | Prefix | Methods | Endpoints |
|---------|--------|---------|-----------|
| S1 | `/api/share` | POST, GET, DELETE | `/generate`, `/{share_id}`, `/list` |
| S2 | `/api/reasoning` | POST | `/think`, `/think/stream` |
| S3 | `/api/artifacts` | GET, POST, PUT, DELETE | `/`, `/{id}` |
| S4 | `/api/chat/upload` | POST | `/` (multipart) |
| S5 | `/api/slash-commands` | GET | `/` |
| S6 | `/api/chat/search` | GET | `/?q=...` |
| S7 | `/api/chat/export` | GET | `/{id}/markdown`, `/{id}/json`, `/{id}/pdf` |
| S8 | `/api/global-memory` | GET, POST, DELETE | `/`, `/{id}` |
| S9 | `/api/prompt-templates` | GET, POST, PUT, DELETE | `/`, `/{id}`, `/{id}/use` |
| S10 | `/api/scheduled-tasks` | GET, POST, PUT, DELETE | `/`, `/{id}`, `/{id}/run` |
| S11 | `/api/branch-conversations` | POST | `/` |
| S12 | `/api/deep-research` | POST, GET | `/start`, `/{id}/status`, `/{id}/report` |

**মোট: ৩২টি API Endpoints**

---

## প্যাচ ফাইল তৈরি করা

সব পরিবর্তন করার পর git diff দিয়ে patch file তৈরি করুন:

```bash
# শুধু Tier-S ফাইলগুলোর জন্য patch

git diff --no-color \
  backend/api/routes/share.py \
  backend/api/routes/reasoning.py \
  backend/api/routes/artifacts.py \
  backend/api/routes/chat_upload.py \
  backend/api/routes/slash_commands.py \
  backend/api/routes/chat_search.py \
  backend/api/routes/chat_export.py \
  backend/api/routes/global_memory.py \
  backend/api/routes/prompt_templates.py \
  backend/api/routes/branch_conversations.py \
  backend/api/routes/scheduled_tasks.py \
  backend/api/routes/deep_research.py \
  backend/api/routes/tier_s_routes.py \
  backend/alembic_migrations/versions/tier_s_features.py \
  backend/api/routers.py \
  backend/api/server.py \
  frontend/src/App.tsx \
  frontend/src/components/share/ShareDialog.tsx \
  frontend/src/components/reasoning/ThinkingPanel.tsx \
  frontend/src/components/artifacts/ArtifactsPanel.tsx \
  frontend/src/components/chat/ImageUploadButton.tsx \
  frontend/src/components/chat/ChatInterface.tsx \
  frontend/src/components/export/ExportMenu.tsx \
  frontend/src/components/branch/BranchButton.tsx \
  frontend/src/components/commands/SlashCommandMenu.tsx \
  frontend/src/components/search/ChatSearchDialog.tsx \
  frontend/src/pages/SharedConversationPage.tsx \
  frontend/src/pages/PromptTemplatePage.tsx \
  frontend/src/store/tierSStore.ts \
  frontend/src/routes/tierSRoutes.tsx \
  frontend/package.json \
  > tier_s_patch.diff

# Patch apply করতে (অন্য machine-এ):
git apply tier_s_patch.diff
```

---

## সম্ভাব্য সমস্যা ও সমাধান

### 1. Migration Error: `relation 