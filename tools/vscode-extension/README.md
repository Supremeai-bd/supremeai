# SupremeAI VS Code Extension

Real-time code learning and AI assistance directly in your IDE. Every code edit, error, and feedback you provide trains the SupremeAI core engine instantly.

## Key Features

- **Zero-Config Thin Client & Offline Fallback**: All AI processing happens securely on the SupremeAI backend. In offline mode, requests can failover to local **Ollama** (`http://localhost:11434/api/chat`).
- **Admin & Customer Dashboards**: Directly integrated inside the VS Code sidebar:
  - **Admin Dashboard**: View system status, active provider, model name, run CodeFlow Analysis, and trigger security audits.
  - **Customer Dashboard**: Track account info, total code edits, accepted suggestions, and easily open chat.
- **SecretStorage Integration**: Dynamically secure API keys and tokens directly in the OS-level credential store.
- **Context Menu & Command Palette**: Quickly send code selections using **"SupremeAI: Send Selected Code to Chat"** via right-click or `Ctrl+Shift+P`.

## Installation

### From Source

1. Clone and install dependencies:

```bash
cd supremeai-vscode-extension
npm install
```

2. Compile TypeScript:

```bash
npm run compile
```

3. Run unit tests:

```bash
npm run unit
```

4. Debug extension:
   - Press `F5` in VS Code to open the Extension Development Host.

## Configuration

Open VS Code Settings (Ctrl+,) and search for `supremeai` to configure `backendUrl` and `performanceMode`.

## License

MIT
