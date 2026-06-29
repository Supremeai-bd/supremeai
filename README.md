# SupremeAI 2.0 🚀
**Autonomic CI/CD Command Center & Neural Agentic Workspace**

SupremeAI is a production-grade, highly scalable ecosystem featuring a Hub-and-Spoke CI/CD pipeline, an AI-powered CodeQL audited backend, and dual real-time client interfaces.

## 🌟 Core Architecture

### 🧠 The Brain (Backend)
- **Framework:** FastAPI (Python)
- **AI Engine:** Google Gemini 1.5 Pro (Generative AI)
- **Streaming:** Native WebSockets (`wss://`) for token-by-token generation.
- **Agentic Tools:** Autonomous tool calling (Database Search, System Health, Code Execution).
- **Security:** `god.py` Constitutional Enforcement (Real-time global write-access toggle).

### 💻 Command Center (Web)
- **Tech Stack:** Pure Vanilla HTML/CSS/JS (Zero framework overhead for maximum speed).
- **Features:** Real-time CI/CD Job Sync (GitHub Raw APIs), Interactive Hacker-style Terminal for logs, 1-Click Quick Actions (Rollback, Cache Flush).

### 📱 Supreme Workspace (Mobile)
- **Tech Stack:** Flutter & Dart (Provider + HTTP + WebSocket Channel).
- **Features:** Real-time AI chat stream, System Monitoring, God Mode enforcement UI.

### ⚙️ CI/CD Pipeline (GitHub Actions)
- **Matrix Builds:** Automatically builds Android APK, Windows EXE, and VS Code VSIX concurrently.
- **Security:** Integrated GitHub CodeQL Semantic Security Analysis on every push.

## 🚀 Getting Started

**Web Dashboard (Dev Mode):**
```bash
cd apps/web-chat
python -m http.server 3000
```

**Mobile App (Dev Mode):**
```bash
cd apps/mobile
flutter pub get
flutter run
```

Built with ❤️ for zero-latency DevSecOps.
