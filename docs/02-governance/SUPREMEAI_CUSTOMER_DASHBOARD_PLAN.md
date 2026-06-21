# SUPREMEAI 2.0 — CUSTOMER DASHBOARD & PERSONALIZED WORKSPACE
# Master Plan: Browser Preview, Mobile Simulator, GitHub Integration & Customizable UI

> **Version:** 2.0.0  
> **Date:** 2026-06-21  
> **Status:** Master Plan — Awaiting Implementation  
> **Vision:** Every user gets their own personalized AI command center tailored to their workflow, tools, and interests

---

## TABLE OF CONTENTS

1. [Vision Statement](#1-vision-statement)
2. [Architecture Philosophy](#2-architecture-philosophy)
3. [Full Customer Dashboard Module Plan](#3-full-customer-dashboard-module-plan)
4. [Current Customer Dashboard Analysis](#4-current-customer-dashboard-analysis)
5. [Gap Analysis: What We're Missing](#5-gap-analysis-what-were-missing)
6. [Implementation Roadmap](#6-implementation-roadmap)
7. [UI/UX Design Principles](#7-uiux-design-principles)
8. [Data Model & Personalization Engine](#8-data-model--personalization-engine)

---

## 1. VISION STATEMENT

> "No two users are the same. A developer needs code preview and GitHub. A designer needs image generation and browser testing. A writer needs research tools and content templates. SupremeAI adapts to YOU — not the other way around."

The Customer Dashboard is not a one-size-fits-all interface. It is a **living workspace** that:

- **Learns your workflow** — Surfaces the tools you use most
- **Adapts to your role** — Developer, Designer, Writer, Researcher, Analyst
- **Integrates your tools** — GitHub, Figma, Notion, Slack, your own APIs
- **Previews your work** — Browser preview, mobile simulator, code output
- **Remembers your context** — Projects, files, conversations, preferences
- **Evolves with you** — Suggests new features based on usage patterns

---

## 2. ARCHITECTURE PHILOSOPHY

### The "Personal AI OS" Metaphor

| Dashboard Section | OS Analog | Purpose |
|------------------|-----------|---------|
| **Home / Feed** | Desktop / Home Screen | Your starting point, widgets, recent activity |
| **AI Chat** | Terminal / Command Line | Talk to your AI assistant |
| **Browser Preview** | Web Browser | See what your AI builds in real-time |
| **Mobile Simulator** | Device Emulator | Test responsive designs instantly |
| **GitHub Connection** | Git Client | Version control, repos, commits, PRs |
| **Project Workspace** | File Explorer | Organize work into projects |
| **Tool Palette** | App Launcher | Quick access to AI tools |
| **Activity Timeline** | Notification Center | What happened, when, why |

### Design Principles

1. **Progressive Disclosure** — Simple by default, powerful when needed
2. **Context Preservation** — Never lose your place, never repeat yourself
3. **Tool Integration** — Work where you already work (GitHub, VS Code, Figma)
4. **Real-time Feedback** — See results as you type, not after you submit
5. **Personalization** — Dashboard rearranges itself based on your behavior
6. **Collaboration** — Share workspaces, co-edit with team members

---

## 3. FULL CUSTOMER DASHBOARD MODULE PLAN

---

### MODULE 0: PERSONALIZED HOME / DASHBOARD FEED

**Purpose:** The user's personal landing page — like a smartphone home screen meets Notion dashboard.

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  👤 Good morning, [Name]!        [Search] [🔔] [⚙️] [👤]   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 🎯 Continue │  │ 📊 Stats    │  │ 🔔 Recent   │          │
│  │  Project X  │  │  Today: 12  │  │  Activity   │          │
│  │  [Resume]   │  │  requests   │  │  • New commit│         │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 🤖 Quick Actions (AI-Powered Shortcuts)             │    │
│  │  [Generate landing page] [Write API docs] [Debug]   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │ 📁 Recent Projects    │  │ 🛠️ Favorite Tools          │  │
│  │ • E-commerce site     │  │ • Code Generator          │  │
│  │ • API documentation   │  │ • Image Generator         │  │
│  │ • Marketing campaign  │  │ • Browser Agent           │  │
│  └─────────────────────┘  └─────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 📈 Activity Timeline                                │    │
│  │ 9:00 AM — Generated React component                  │    │
│  │ 9:15 AM — Pushed to GitHub (commit: abc123)        │    │
│  │ 9:30 AM — Deployed to preview URL                    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Widgets (User-Customizable):**
- **Continue Where You Left Off** — Last project, last file, last conversation
- **Daily Stats** — Requests made, tokens used, time saved
- **Quick Actions** — AI-suggested next steps based on context
- **Recent Projects** — Cards with preview thumbnails, last edited time
- **Favorite Tools** — Pin tools you use most (drag to reorder)
- **Activity Timeline** — Chronological feed of everything you did
- **Team Activity** — What your teammates are working on (if in team)
- **AI Insights** — "You generate most code on Tuesdays" — pattern detection
- **Upcoming Deadlines** — From connected calendars (Google, Outlook)
- **News Feed** — AI industry news, new features in SupremeAI

**Personalization Engine:**
- Tracks which widgets you interact with → hides unused, promotes used
- Time-aware: Morning = "Continue projects", Evening = "Review today's work"
- Role-aware: Developer sees code widgets, Designer sees image widgets

---

### MODULE 1: AI CHAT INTERFACE (Enhanced)

**Purpose:** The core interaction — talking to SupremeAI. But smarter.

**Current State:** Basic chat with text input
**Target State:** Rich, contextual, multimodal chat

**Features:**

#### 1.1 Context-Aware Chat
- **Project Context:** "In Project X, generate a navbar component" — AI knows your project structure
- **File Context:** Drag-drop a file → AI reads and discusses it
- **Conversation Memory:** "Remember I said I prefer Tailwind?" — AI recalls preferences
- **Persona Modes:**
  - 🧑‍💻 **Code Mode** — Concise, technical, code-first
  - 🎨 **Design Mode** — Visual, descriptive, aesthetic-focused
  - 📝 **Writing Mode** — Creative, narrative, tone-aware
  - 🔬 **Research Mode** — Thorough, cited, analytical
  - 🏢 **Business Mode** — Professional, data-driven, ROI-focused

#### 1.2 Rich Message Types
- **Text** (current) — Plain text responses
- **Code Blocks** — Syntax highlighted, copy button, open in editor
- **Images** — Generated images, diagrams, screenshots
- **Files** — Downloadable outputs (PDF, CSV, JSON, ZIP)
- **Interactive Cards** — "Here's your component — [Preview] [Edit] [Deploy]"
- **Embeds** — YouTube videos, Figma files, GitHub repos rendered inline
- **Tables** — Data tables with sort, filter, export
- **Charts** — Auto-generated charts from data discussions

#### 1.3 Inline Actions
- **"Try it" Button** — For code: opens in Browser Preview instantly
- **"Save to Project"** — File output → auto-saves to current project
- **"Share"** — Generate shareable link or export to Slack/Discord
- **"Fork"** — Create variation of this output
- **"Explain"** — AI explains its own response in simpler terms
- **"Improve"** — AI critiques and improves its own output

#### 1.4 Split-View Chat
```
┌────────────────────────────┬─────────────────────────────┐
│  💬 Chat                    │  👁️ Preview / Output        │
│                             │                             │
│  User: Build a login page   │  ┌─────────────────────┐   │
│                             │  │  [Live Preview]      │   │
│  AI: Here's your login...   │  │                     │   │
│                             │  │  [Username]         │   │
│  [Try it] [Save] [Share]    │  │  [Password]         │   │
│                             │  │  [Login Button]     │   │
│  User: Make it dark mode    │  │                     │   │
│                             │  └─────────────────────┘   │
│  AI: Updated!               │  [🌐 Open in Browser]      │
│                             │  [📱 Mobile View]           │
└────────────────────────────┴─────────────────────────────┘
```

---

### MODULE 2: BROWSER PREVIEW ENGINE

**Purpose:** See what your AI builds — instantly, in a real browser.

**Current State:** None (users must download or manually test)
**Target State:** Built-in browser preview with dev tools

#### 2.1 Live Preview Panel
- **Real-time rendering** — As AI generates HTML/CSS/JS, preview updates live
- **Multi-tab support** — Preview multiple pages simultaneously
- **URL bar** — Navigate to any URL (for web scraping, testing)
- **Refresh / Hard refresh** — Standard browser controls
- **Console output** — See JavaScript errors and logs
- **Responsive breakpoints** — Toggle desktop/tablet/mobile instantly

#### 2.2 Preview Modes
- **Standalone Preview** — Full tab dedicated to preview
- **Split Preview** — Chat on left, preview on right (see above)
- **Popup Preview** — Floating window you can drag around
- **External Preview** — Open in your actual browser with hot-reload

#### 2.3 Interactive Preview
- **Click-to-edit** — Click an element in preview → AI edits that specific element
- **Inspect Element** — Right-click → "Inspect" → shows HTML/CSS in sidebar
- **Device Simulation** — iPhone 14, Pixel 7, iPad, custom dimensions
- **Network Throttling** — Simulate slow 3G, fast 4G, offline
- **Dark/Light mode toggle** — Test both themes

#### 2.4 Preview from URL
- **Scrape & Preview** — "Show me how amazon.com renders on mobile"
- **Screenshot comparison** — Side-by-side before/after redesigns
- **Accessibility audit** — Run Lighthouse in preview, show scores

#### 2.5 Backend Architecture for Preview
```
Frontend Request → Cloud Run Preview Service (isolated container)
                   → Spins up headless Chrome (Puppeteer/Playwright)
                   → Renders HTML/CSS/JS
                   → Streams screenshot + console logs via WebSocket
                   → Auto-destroys container after 5 min idle
```

---

### MODULE 3: MOBILE SIMULATOR

**Purpose:** Test how AI-generated content looks on real mobile devices — without leaving the dashboard.

**Current State:** None
**Target State:** Full device simulation lab

#### 3.1 Device Frame Simulator
```
┌─────────────────────────────────────────────────────────────┐
│  📱 Mobile Simulator Lab                                    │
├─────────────────────────────────────────────────────────────┤
│  Device: [iPhone 14 ▼]  Orientation: [Portrait ▼]           │
│  OS: [iOS 17 ▼]  Scale: [100% ▼]                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│     ┌─────────────────────┐                                │
│     │  🔋 9:41  📶 5G     │  ← Realistic device frame      │
│     │                     │                                │
│     │  [Your AI-generated  │                                │
│     │   mobile app/site   │                                │
│     │   renders here]     │                                │
│     │                     │                                │
│     │  [Home] [Share]     │  ← Touch-friendly controls     │
│     └─────────────────────┘                                │
│                                                              │
│  [📷 Screenshot] [🎥 Record] [📊 Performance]               │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2 Device Library
- **iOS Devices:** iPhone SE, 12, 13, 14, 14 Pro, 15, 15 Pro, iPad, iPad Pro
- **Android Devices:** Pixel 6, 7, 8, Samsung Galaxy S23, S24, Fold
- **Custom:** Enter any width × height
- **Wearables:** Apple Watch, Android Wear (for micro-apps)

#### 3.3 Touch Simulation
- **Touch events** — Click simulates tap, scroll simulates swipe
- **Multi-touch** — Pinch to zoom (Ctrl+scroll), rotate
- **Haptic feedback** — Visual shake on "haptic" events
- **Gesture recording** — Record and replay touch sequences

#### 3.4 Mobile-Specific Testing
- **Viewport testing** — Safe areas, notches, dynamic island
- **Keyboard simulation** — Text input triggers virtual keyboard
- **Orientation change** — Rotate device, test landscape/portrait
- **Performance metrics** — FPS, memory, battery impact simulation
- **Network conditions** — Offline, 2G, 3G, 4G, WiFi

#### 3.5 Flutter App Preview (Special)
Since you have a Flutter mobile app:
- **Hot reload** — Code changes reflect instantly in simulator
- **Widget inspector** — Tap any widget → see its properties
- **State management** — Inspect Provider/Riverpod state
- **Route navigation** — Test deep links, push/pop navigation

---

### MODULE 4: GITHUB INTEGRATION

**Purpose:** Connect your AI workspace directly to your code repositories.

**Current State:** None
**Target State:** Deep GitHub integration — like GitHub Copilot meets your dashboard

#### 4.1 Repository Browser
```
┌─────────────────────────────────────────────────────────────┐
│  🔗 GitHub Integration                                        │
├─────────────────────────────────────────────────────────────┤
│  Connected as: @paykaribazaronline                          │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 📁 Your Repositories                                │    │
│  │ • supremeai                    ⭐ 12  🍴 3  🟢 JS   │    │
│  │ • paykaribazaronline.github.io  ⭐ 5   🍴 1  🟣 CSS │    │
│  │ • ai-tools-collection          ⭐ 8   🍴 2  🟡 Py  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 📝 Recent Activity                                  │    │
│  │ • You pushed to supremeai/main (2 min ago)          │    │
│  │ • PR #42 merged by @teammate (1 hour ago)           │    │
│  │ • Issue #15 assigned to you (3 hours ago)           │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

#### 4.2 AI-Powered GitHub Actions
- **"Generate PR Description"** — AI writes PR summary from diff
- **"Review this PR"** — AI reviews code, suggests improvements
- **"Fix this issue"** — AI reads issue, generates fix, creates PR
- **"Explain this commit"** — AI explains what changed and why
- **"Find similar code"** — Search across repos for patterns

#### 4.3 Code Sync
- **Push to GitHub** — "Save this component to my repo"
- **Pull from GitHub** — "Import this file into my project"
- **Branch management** — Create, switch, merge branches from dashboard
- **Conflict resolution** — AI suggests how to resolve merge conflicts
- **Commit history** — Visual timeline of commits, clickable to see diff

#### 4.4 GitHub Issues & Projects
- **Issue creation** — "Create issue: Fix navbar on mobile" → AI generates detailed issue
- **Issue triage** — AI categorizes and prioritizes incoming issues
- **Project boards** — Kanban view of GitHub Projects, drag-drop cards
- **Milestone tracking** — Progress bars, burndown charts

#### 4.5 GitHub Copilot Alternative
- **Inline code suggestions** — As you type in the dashboard editor
- **"Generate tests"** — AI writes unit tests for selected function
- **"Refactor this"** — AI suggests cleaner code structure
- **"Document this"** — AI generates JSDoc/docstrings

#### 4.6 GitHub API Integration Architecture
```
User OAuth → GitHub App (installed on repos)
           → Webhooks for real-time updates (push, PR, issues)
           → SupremeAI backend caches repo metadata
           → Frontend shows live data via WebSocket
           → AI can read/write code via GitHub API
```

---

### MODULE 5: PROJECT WORKSPACE

**Purpose:** Organize all your AI work into structured projects — like VS Code workspaces meets Notion.

**Current State:** None (all conversations are ephemeral)
**Target State:** Persistent project-based organization

#### 5.1 Project Structure
```
📁 My Projects
├── 🚀 E-commerce Website
│   ├── 📄 requirements.md
│   ├── 📁 components/
│   │   ├── Navbar.tsx (AI-generated)
│   │   ├── HeroSection.tsx (AI-generated)
│   │   └── Footer.tsx (AI-generated)
│   ├── 📁 assets/
│   │   ├── logo.png (AI-generated)
│   │   └── hero-bg.jpg (AI-generated)
│   ├── 📄 preview.html
│   └── 💬 conversations/
│       ├── "Initial design discussion"
│       ├── "Navbar revisions"
│       └── "Final review"
│
├── 📱 Fitness App
│   ├── 📄 app-spec.md
│   ├── 📁 screens/
│   ├── 📁 api/
│   └── 💬 conversations/
│
└── 🤖 AI Chatbot for Customer Support
    ├── 📄 personality.md
    ├── 📁 training-data/
    └── 💬 conversations/
```

#### 5.2 Project Creation
- **From template** — "E-commerce site", "Mobile app", "Landing page", "API backend"
- **From GitHub repo** — Import existing repo as project
- **From scratch** — Blank project, build as you go
- **AI-generated** — "Create a project for a food delivery app" → AI scaffolds everything

#### 5.3 Project Dashboard
- **Files tab** — File tree with preview, edit, delete
- **Chat tab** — All conversations related to this project
- **Preview tab** — Live preview of the project
- **Settings tab** — Project config, env vars, collaborators
- **Deploy tab** — Deploy to Vercel, Netlify, Cloudflare Pages

#### 5.4 Collaboration
- **Share project** — Invite by email, generate link
- **Real-time co-editing** — Multiple users editing same file (like Google Docs)
- **Comments** — Comment on specific lines of code/output
- **Version history** — Time-machine for project files
- **Branches** — Experiment without breaking main project

---

### MODULE 6: CUSTOMIZABLE TOOL PALETTE

**Purpose:** Each user configures their own toolbox — drag, drop, rearrange.

**Current State:** Fixed sidebar with presets
**Target State:** Fully customizable tool grid

#### 6.1 Tool Categories
| Category | Tools |
|----------|-------|
| **Code** | Code Generator, Code Explainer, Bug Fixer, Test Generator, Refactorer |
| **Design** | Image Generator, UI Component Builder, Color Palette, Icon Generator |
| **Content** | Writer, Translator, Summarizer, SEO Optimizer, Email Composer |
| **Data** | CSV Analyzer, Chart Generator, SQL Query Builder, Data Cleaner |
| **Media** | Video Generator, Voice Generator, Music Generator, Podcast Creator |
| **Research** | Web Scraper, PDF Analyzer, Citation Finder, Fact Checker |
| **DevOps** | Dockerfile Generator, CI/CD Config, Terraform Generator, K8s YAML |
| **Business** | Pitch Deck, Business Plan, Financial Model, Competitor Analysis |
| **Custom** | User-defined tools via API integration |

#### 6.2 Customization Options
- **Pin favorites** — Right-click → "Pin to dashboard"
- **Reorder** — Drag and drop tools in any order
- **Hide unused** — "I never use video tools" → hide category
- **Create bundles** — "My Dev Bundle" = Code + Test + Docker + CI/CD
- **Keyboard shortcuts** — Cmd+1 for first tool, Cmd+2 for second, etc.
- **Quick search** — Cmd+K → type "docker" → jumps to Dockerfile Generator

#### 6.3 Tool Builder (Advanced)
- **Custom tool creation** — "I want a tool that does X"
- **Prompt template** — Define input fields, AI prompt template, output format
- **API integration** — Connect external APIs as tools
- **Share tools** — Publish to marketplace, earn credits

---

### MODULE 7: ACTIVITY TIMELINE & ANALYTICS

**Purpose:** See everything you've done — and learn from it.

#### 7.1 Personal Analytics
- **Usage dashboard** — Requests/day, tokens consumed, cost breakdown
- **Productivity score** — Time saved vs manual work
- **Skill growth** — "You've mastered React components" — based on usage
- **Peak hours** — When you're most productive
- **Favorite models** — "You use GPT-4 70% of the time"

#### 7.2 Activity Feed
```
Today
├── 9:00 AM — Generated React navbar component
├── 9:15 AM — Edited component in Browser Preview
├── 9:20 AM — Pushed to GitHub (supremeai/web-components)
├── 9:30 AM — Created PR #47: "Add responsive navbar"
├── 10:00 AM — Generated 3 hero images for landing page
├── 10:30 AM — Deployed preview to Vercel
└── 11:00 AM — Shared project with @teammate

Yesterday
├── ...

This Week
├── 47 requests, 12 projects touched, $2.34 spent
```

#### 7.3 Achievement System (Gamification)
- **Badges** — "First Deployment", "10K Tokens", "Code Ninja", "Design Guru"
- **Streaks** — "7-day coding streak"
- **Milestones** — "100 projects created", "1M tokens consumed"
- **Leaderboard** — Team leaderboard (optional, opt-in)

---

### MODULE 8: SETTINGS & PREFERENCES

**Purpose:** Make SupremeAI truly yours.

#### 8.1 Profile Settings
- **Display name, avatar, bio**
- **Role selection** — Developer, Designer, Writer, Researcher, Business, Student, Other
- **Role affects dashboard** — Developer sees code tools first, Designer sees image tools
- **Language preference** — Bengali, English, and 50+ more
- **Timezone, date format, currency**

#### 8.2 AI Preferences
- **Default model** — "Always use GPT-4 for code"
- **Response style** — Concise / Detailed / Technical / Simple
- **Code preferences** — Language (JS/TS/Python), framework (React/Vue/Angular), styling (Tailwind/CSS-in-JS)
- **Output format** — Markdown, HTML, JSON, plain text
- **Auto-save** — Save every output to project? Yes/No

#### 8.3 Notification Settings
- **Channels** — Email, Browser push, Slack, Discord
- **Events** — Deployment complete, PR merged, teammate mention, cost alert
- **Digest** — Daily/weekly summary of activity

#### 8.4 Integration Settings
- **GitHub** — Connect/disconnect, select default org
- **Figma** — Import designs, export to Figma
- **Notion** — Export conversations to Notion pages
- **Slack/Discord** — Bot integration, channel notifications
- **VS Code** — Extension settings, sync preferences
- **Custom API** — Add your own API endpoints as tools

#### 8.5 Privacy & Data
- **Data export** — Download all your conversations, projects, files
- **Data deletion** — "Delete all my data" (GDPR/CCPA compliant)
- **Conversation privacy** — "Don't save this conversation"
- **AI training opt-out** — "Don't use my data to improve models"

---

## 4. CURRENT CUSTOMER DASHBOARD ANALYSIS

### What Exists in `OperatorStudio.tsx`:

| Feature | Status | Quality |
|---------|--------|---------|
| **AI Chat** | ✅ Basic | Text only, no rich output |
| **Quick Presets** | ✅ Present | 3 hardcoded buttons (Code, Translate, Write) |
| **Monaco Editor** | ✅ Present | Code editor, but not connected to preview |
| **Chat History** | ✅ Basic | In-memory only, no persistence |
| **Loading State** | ✅ Present | "SupremeAI is thinking..." |
| **Browser Preview** | ❌ Missing | No way to see generated code |
| **Mobile Simulator** | ❌ Missing | No mobile testing |
| **GitHub Integration** | ❌ Missing | No code sync |
| **Project Workspace** | ❌ Missing | No file organization |
| **Customizable Tools** | ❌ Missing | Fixed sidebar |
| **Activity Timeline** | ❌ Missing | No history |
| **Analytics** | ❌ Missing | No usage stats |
| **Settings** | ❌ Missing | No preferences |
| **Collaboration** | ❌ Missing | Single user only |

### Current Architecture:
- **Single file:** `OperatorStudio.tsx` (6.3KB) + `App.tsx` (19KB)
- **No state management** — Local useState only
- **No persistence** — Refresh = lose everything
- **No real-time** — Polling or nothing
- **No external integrations** — Standalone only

---

## 5. GAP ANALYSIS: WHAT WE'RE MISSING

### Critical Gaps (Must-Have for "Personal AI Workspace")

| # | Missing Feature | Impact | Priority |
|---|----------------|--------|----------|
| 1 | **Browser Preview Engine** | Can't see what AI builds | 🔴 P0 |
| 2 | **Project Persistence** | Lose all work on refresh | 🔴 P0 |
| 3 | **GitHub Integration** | Can't sync code to repos | 🔴 P0 |
| 4 | **Customizable Dashboard** | One-size-fits-all doesn't work | 🔴 P0 |
| 5 | **Mobile Simulator** | Can't test responsive designs | 🟡 P1 |
| 6 | **Rich Output Types** | Only text, no images/charts/files | 🟡 P1 |
| 7 | **Activity Timeline** | No record of what was done | 🟡 P1 |
| 8 | **AI Persona Modes** | Same tone for all tasks | 🟡 P1 |
| 9 | **Collaboration** | Can't work with teammates | 🟢 P2 |
| 10 | **Analytics & Insights** | Don't know usage patterns | 🟢 P2 |
| 11 | **Tool Builder** | Can't add custom tools | 🟢 P2 |
| 12 | **External Integrations** | Figma, Notion, Slack, etc. | 🟢 P2 |
| 13 | **Achievement System** | No engagement/motivation | 🔵 P3 |
| 14 | **Advanced Settings** | No personalization | 🔵 P3 |

### Technical Debt Gaps

| # | Issue | Current State | Target |
|---|-------|--------------|--------|
| 1 | **State persistence** | useState (lost on refresh) | Zustand + localStorage/DB |
| 2 | **File management** | None | Project-based file tree |
| 3 | **Real-time preview** | None | WebSocket streaming |
| 4 | **External APIs** | None | GitHub API, OAuth, webhooks |
| 5 | **Responsive design** | Desktop only | Mobile-first responsive |
| 6 | **Component splitting** | Large files | Modular architecture |

---

## 6. IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Week 1-2)
- [ ] Refactor `OperatorStudio.tsx` into modular components
- [ ] Set up Zustand for state management with persistence
- [ ] Set up React Query for data fetching
- [ ] Add localStorage persistence for chat history
- [ ] Create shared component library (ChatBubble, CodeBlock, FileCard, etc.)

### Phase 2: Core Experience (Week 3-4)
- [ ] **Module 1:** Enhanced Chat with rich output (code, images, files)
- [ ] **Module 5:** Basic Project Workspace (create, save, load projects)
- [ ] **Module 0:** Personalized Home with widgets
- [ ] **Module 6:** Customizable Tool Palette (pin, reorder, hide)

### Phase 3: Power Features (Week 5-6)
- [ ] **Module 2:** Browser Preview Engine (iframe-based, live reload)
- [ ] **Module 4:** GitHub OAuth + basic repo browser
- [ ] **Module 3:** Mobile Simulator (device frames, touch events)
- [ ] **Module 1:** AI Persona Modes (Code, Design, Write, Research)

### Phase 4: Intelligence (Week 7-8)
- [ ] **Module 7:** Activity Timeline + Analytics
- [ ] **Module 4:** AI-powered GitHub actions (PR review, issue fixing)
- [ ] **Module 6:** Tool Builder (custom tool creation)
- [ ] **Module 1:** Context-aware chat (project context, file context)

### Phase 5: Polish (Week 9-10)
- [ ] Mobile responsiveness
- [ ] Dark/light mode
- [ ] Collaboration (share projects, co-edit)
- [ ] External integrations (Figma, Notion, Slack)
- [ ] Achievement system
- [ ] Performance optimization

---

## 7. UI/UX DESIGN PRINCIPLES

### Visual Language
- **Theme:** "Personal AI Workspace" — Clean, modern, distraction-free
- **Color palette:**
  - Background: `#0f1117` (deep space)
  - Surface: `#1a1d29` (panel)
  - Primary accent: `#6366f1` (indigo — user actions)
  - Success: `#22c55e` (green)
  - Warning: `#f59e0b` (amber)
  - Danger: `#ef4444` (red)
  - Preview accent: `#10b981` (emerald — preview/live)
- **Typography:** Inter for UI, JetBrains Mono for code
- **Icons:** Lucide React

### Layout Patterns
- **Sidebar:** Collapsible, icon + label, grouped by module
- **Main area:** Tabbed workspace (Chat | Preview | Files | Settings)
- **Bottom panel:** Collapsible terminal/logs
- **Right panel:** Contextual sidebar (file tree, tool palette, properties)
- **Command palette:** Cmd+K to search anything

### Interaction Patterns
- **Auto-save** — Never lose work
- **Undo/Redo** — Ctrl+Z everywhere
- **Drag-drop** — Files, tools, widgets
- **Keyboard-first** — Power user shortcuts
- **Progressive disclosure** — Simple default, advanced on demand

---

## 8. DATA MODEL & PERSONALIZATION ENGINE

### User Profile Schema
```typescript
interface UserProfile {
  id: string;
  email: string;
  displayName: string;
  avatar: string;
  role: 'developer' | 'designer' | 'writer' | 'researcher' | 'business' | 'student' | 'other';
  preferences: {
    defaultModel: string;
    responseStyle: 'concise' | 'detailed' | 'technical' | 'simple';
    codeLanguage: string;
    framework: string;
    styling: string;
    theme: 'dark' | 'light' | 'system';
    language: string;
    timezone: string;
  };
  dashboard: {
    widgets: WidgetConfig[];
    toolOrder: string[];
    hiddenTools: string[];
    pinnedProjects: string[];
  };
  usage: {
    totalRequests: number;
    totalTokens: number;
    totalCost: number;
    favoriteTools: Record<string, number>;
    peakHours: number[];
    streakDays: number;
  };
  integrations: {
    github?: { connected: boolean; username: string; repos: string[] };
    figma?: { connected: boolean; accessToken: string };
    notion?: { connected: boolean; workspace: string };
    slack?: { connected: boolean; channel: string };
  };
}
```

### Personalization Engine Logic
```typescript
// Pseudocode for dashboard personalization
function personalizeDashboard(user: UserProfile): DashboardConfig {
  // 1. Role-based defaults
  const roleDefaults = getRoleDefaults(user.role);

  // 2. Usage-based recommendations
  const recommendedTools = getTopTools(user.usage.favoriteTools, 5);

  // 3. Time-based widgets
  const timeWidgets = getTimeAppropriateWidgets(new Date());

  // 4. Project context
  const recentProjects = getRecentProjects(user.id, 3);

  // 5. Merge and return
  return mergeConfigs(roleDefaults, user.dashboard, {
    widgets: [...timeWidgets, ...recommendedTools, ...recentProjects],
    toolOrder: user.dashboard.toolOrder.length > 0 
      ? user.dashboard.toolOrder 
      : roleDefaults.toolOrder,
  });
}
```

---

## APPENDIX: RECOMMENDED TECH STACK

| Layer | Current | Recommended |
|-------|---------|-------------|
| **Framework** | React 19 | React 19 + Next.js 14 (App Router) |
| **State** | useState | Zustand (persist middleware) |
| **Data Fetch** | Inline fetch | React Query + Axios |
| **Styling** | Tailwind | Tailwind + shadcn/ui |
| **Icons** | Unknown | Lucide React |
| **Charts** | None | Recharts |
| **Editor** | Monaco | Monaco (keep) + add preview panel |
| **Preview** | None | iframe + Puppeteer (backend) |
| **Mobile Sim** | None | CSS device frames + touch simulation |
| **GitHub** | None | Octokit.js + OAuth |
| **Storage** | None | IndexedDB (local) + Supabase (cloud) |
| **Real-time** | None | Socket.io or native WebSocket |
| **Testing** | Vitest | Vitest + Playwright |

---

*End of Customer Dashboard Master Plan*
