# SupremeAI Unified Client Hub (`supremeai-vscode`)

Native client applications and developer workflows for SupremeAI.  
Per [`ARCHITECTURE_PLAN.md`](https://github.com/Supremeai-bd/supremeai/blob/main/ARCHITECTURE_PLAN.md), this hub hosts desktop and IDE client applications, while the native Android app lives in [`Supremeai-bd/supremeai-apk`](https://github.com/Supremeai-bd/supremeai-apk):

| Client Application | Repository | Target Platform | Release Artifacts |
|---|---|---|---|
| **IDE Extension** | [`Supremeai-bd/supremeai-vscode`](https://github.com/Supremeai-bd/supremeai-vscode) | VS Code / Cursor / Windsurf | `.vsix` Packages & VS Code Marketplace |
| **Desktop Workstation** | [`Supremeai-bd/supremeai-desktop`](https://github.com/Supremeai-bd/supremeai-desktop) | Windows / macOS / Linux | `.exe`, `.msi`, `.dmg`, `.AppImage` |
| **Mobile Studio** | [`Supremeai-bd/supremeai-apk`](https://github.com/Supremeai-bd/supremeai-apk) | Android Phones & Tablets | `.apk` Installers & Google Play Store |
| **Web Studio** | [`Supremeai-bd/supremeai-frontend`](https://github.com/Supremeai-bd/supremeai-frontend) | Web Browsers | Cloud Web Application |

> **Satellite Sovereignty Policy**:
> All external client applications are decoupled into sovereign satellite repositories under the `Supremeai-bd` organization.
> The root repository `Supremeai-bd/supremeai` serves exclusively as the single source of truth for the **AI Core Engine, Gateway Router, Swarm Supervisor, and MCP Control Plane**.

---

## 🛠️ Quick Start

```bash
# Install dependencies across all workspaces
npm install

# Compile the VS Code extension
npm run build:extension

# Run extension tests
npm run test
```
