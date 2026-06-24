# 🖥️ SupremeAI 2.0 Windows Desktop App — Full Implementation Plan

## 📋 Current Architecture Overview

| Component | Technology | Status |
|-----------|-----------|--------|
| Backend API | FastAPI (Python) | ✅ Production (Cloud Run) |
| Web Chat | React + Vite | ✅ Exists (`apps/web-chat`) |
| Studio Client | React + Vite | ✅ Exists (`apps/studio-client`) |
| Mobile App | Flutter | ✅ Exists (`apps/mobile`) |
| VS Code Extension | TypeScript | ✅ Exists |
| **Desktop/Windows App** | **❌ NONE** | **🎯 TARGET** |

---

## 🏆 Recommendation: Tauri + React

**Why Tauri over Electron:**
1. **Performance:** Native Rust core, not Chromium.
2. **Size:** 5-15MB vs 150MB+ (Electron).
3. **Security:** OS-level sandbox, not browser sandbox.
4. **Reuse:** Can import `studio-client` React components.
5. **Features:** Native file system, system tray, global shortcuts, notifications.
6. **Auto-update:** Built-in updater with signature verification.
7. **CI/CD:** Easy GitHub Actions integration.

---

## 📁 Proposed Directory Structure

```text
supremeai/
├── apps/
│   ├── desktop/                    # 🆕 NEW: Windows Desktop App
│   │   ├── src/
│   │   │   ├── main.rs            # Tauri Rust backend
│   │   │   ├── lib.rs             # Commands & native APIs
│   │   │   └── tray.rs            # System tray handler
│   │   ├── src-tauri/
│   │   │   ├── Cargo.toml         # Rust dependencies
│   │   │   ├── tauri.conf.json    # App config
│   │   │   ├── icons/             # App icons
│   │   │   └── build.rs           # Build script
│   │   ├── src-ui/                # React frontend
│   │   │   ├── src/
│   │   │   │   ├── App.tsx        # Main app
│   │   │   │   ├── components/    # Reusable components
│   │   │   │   ├── pages/         # Page components
│   │   │   │   ├── hooks/         # Custom hooks
│   │   │   │   ├── services/      # API services
│   │   │   │   ├── stores/        # State management (Zustand)
│   │   │   │   └── types/         # TypeScript types
│   │   │   ├── package.json
│   │   │   └── vite.config.ts
│   │   ├── wix/                   # Windows Installer
│   │   │   ├── supremeai.wxs      # WiX source
│   │   │   └── build.ps1          # Build script
│   │   └── package.json           # Workspace config
│   ├── mobile/                    # Existing Flutter
│   ├── studio-client/             # Existing React
│   ├── web-chat/                  # Existing React
│   └── vscode/                    # Existing Extension
├── backend/                       # Existing FastAPI
└── packages/
    ├── shared-types/              # Shared TypeScript types
    └── ui-components/             # Shared React components
```

---

## 🔌 API Integration Layer

### Backend Communication
```typescript
// apps/desktop/src-ui/src/services/api.ts
import { fetch } from '@tauri-apps/plugin-http';

const API_BASE = 'https://api.supremeai.dev'; // or self-hosted

export const supremeApi = {
  // Auth
  login: (token: string) => localStorage.setItem('jwt', token),

  // Chat
  sendMessage: async (message: string) => {
    return fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${getToken()}` },
      body: JSON.stringify({ message })
    });
  },

  // Skills
  listSkills: () => fetch(`${API_BASE}/api/skills`),
  executeSkill: (name: string, params: any) => 
    fetch(`${API_BASE}/api/skills/${name}/execute`, { method: 'POST', body: JSON.stringify(params) }),

  // Evolution
  forgeSkill: (demand: string) => 
    fetch(`${API_BASE}/api/evolution/forge`, { method: 'POST', body: JSON.stringify({ skill_name: demand, user_demand: demand }) }),

  // GitHub
  connectRepo: (url: string) => 
    fetch(`${API_BASE}/api/github/connect`, { method: 'POST', body: JSON.stringify({ repo_url: url }) }),

  // Admin
  getLogs: () => fetch(`${API_BASE}/admin-api/logs/stream`),
  getCosts: () => fetch(`${API_BASE}/admin-api/costs`),
};
```

---

## 🎨 UI/UX Design Plan

### Main Window Layout
```text
┌─────────────────────────────────────────────────────────────┐
│  SupremeAI 2.0                              [_] [□] [X]    │
├──────────┬──────────────────────────────────────────────────┤
│          │  💬 Chat                                          │
│  🤖 AI   │  ┌─────────────────────────────────────────────┐  │
│  ├ Chat  │  │ User: Write a Twitter thread about AI      │  │
│  ├ Skills│  │                                              │  │
│  ├ Tools │  │ 🤖 SupremeAI: Here's a 5-tweet thread...   │  │
│  ├ GitHub│  │                                              │  │
│  ├ Evolve│  │ [Regenerate] [Copy] [Execute as Skill]     │  │
│  ├ Market│  └─────────────────────────────────────────────┘  │
│  ├ Admin │                                                   │
│  └ Settings│  📝 Input: [Type your message...        ] [➤] │
│          │                                                   │
│  🔧 Tools│  ⚡ Quick Actions:                               │
│  ├ Code  │  [🐦 Twitter] [📸 Instagram] [💻 Code] [🎨 Design]│
│  ├ Image │  [📊 Data] [🔍 SEO] [✍️ Write] [🎤 Voice]       │
│  ├ Voice │                                                   │
│  └ File  │  📊 Token Usage: 1,234 / 10,000                │
│          │  💰 Cost: $0.12 this session                    │
└──────────┴───────────────────────────────────────────────────┘
```

### Key Native Features
1. **Global Hotkey** (`Ctrl+Shift+S`) — Open app from anywhere.
2. **System Tray** — Minimize to tray, quick actions.
3. **Native Notifications** — Job complete, error alerts.
4. **File Drag & Drop** — Directly drop into chat.
5. **Auto-Start** — Launch on Windows startup.
6. **Offline Mode** — Queue requests when offline.
7. **Multi-Window** — Multiple concurrent chat sessions.

---

## 🦀 Tauri Rust Backend

```rust
// apps/desktop/src-tauri/src/main.rs
use tauri::Manager;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            // System tray setup
            let tray = tauri::SystemTray::new()
                .with_menu(tauri::SystemTrayMenu::new()
                    .add_item(tauri::CustomMenuItem::new("show", "Show SupremeAI"))
                    .add_item(tauri::CustomMenuItem::new("quick_chat", "Quick Chat"))
                    .add_native_item(tauri::SystemTrayMenuItem::Separator)
                    .add_item(tauri::CustomMenuItem::new("quit", "Quit")));

            // Global hotkey: Ctrl+Shift+S
            app.global_shortcut_manager()
                .register("Ctrl+Shift+S", || {
                    // Show/hide window logic
                })?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            execute_skill,
            read_local_file,
            write_local_file,
            show_notification,
            get_system_info,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
async fn execute_skill(name: String, params: serde_json::Value) -> Result<String, String> {
    // Call backend API
    Ok("result".into())
}

#[tauri::command]
fn read_local_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(path).map_err(|e| e.to_string())
}

#[tauri::command]
fn show_notification(title: String, body: String) {
    tauri::api::notification::Notification::new("com.supremeai.app")
        .title(title)
        .body(body)
        .show()
        .unwrap();
}
```

---

## 🔄 Auto-Update System

```rust
// In main.rs
use tauri_plugin_updater::UpdaterExt;

// Check for updates on startup
app.updater()
    .check()
    .await?
    .map(|update| {
        update.download_and_install(|_, _| {}, || {}).await?;
    });
```

---

## 🚀 CI/CD Pipeline (GitHub Actions)

> [!NOTE]
> The GitHub action below will build the Tauri application and package it as an `.msi` file automatically on every version tag. 

```yaml
# .github/workflows/desktop-release.yml
name: 🖥️ Desktop App Release

on:
  push:
    tags: ['desktop-v*']

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Setup Rust
        uses: dtolnay/rust-action@stable

      - name: Install Tauri CLI
        run: npm install -g @tauri-apps/cli

      - name: Install dependencies
        working-directory: apps/desktop/src-ui
        run: npm ci

      - name: Build Tauri App
        working-directory: apps/desktop
        run: tauri build

      - name: Upload to GitHub Releases
        uses: softprops/action-gh-release@v1
        with:
          files: |
            apps/desktop/src-tauri/target/release/SupremeAI.exe
            apps/desktop/src-tauri/target/release/bundle/msi/*.msi
```

---

## 📋 Implementation Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Phase 1: Setup** | 2 days | Tauri project scaffold, shared types, build pipeline |
| **Phase 2: Core UI** | 5 days | Main window, chat interface, navigation, theme |
| **Phase 3: API Integration** | 3 days | Auth, chat, skills, evolution API hooks |
| **Phase 4: Native Features** | 3 days | System tray, global hotkey, notifications, file drag-drop |
| **Phase 5: Polish** | 2 days | Auto-update, installer, icons, error handling |
| **Phase 6: Testing** | 2 days | Windows 10/11 testing, performance, security |
| **Phase 7: Release** | 1 day | Code signing, GitHub release, website update |
| **TOTAL** | **~18 days** | |

## User Review Required
> [!IMPORTANT]
> The plan is ready to be executed. Please click **Proceed** if you would like me to initialize the Tauri workspace in `apps/desktop`!
