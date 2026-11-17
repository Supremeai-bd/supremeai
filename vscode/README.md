# SupremeAI Unified Client Hub (`supremeai-vscode`)

Native client applications and developer workflows for SupremeAI.  
Per [`ARCHITECTURE_PLAN.md`](https://github.com/Supremeai-bd/supremeai/blob/main/ARCHITECTURE_PLAN.md), this hub hosts desktop and IDE client applications, while the native Android app lives in [`Supremeai-bd/supremeai-apk`](https://github.com/Supremeai-bd/supremeai-apk):

| Subdirectory / Repo | Target Platform | Release Channel |
|---|---|---|
| **[`/extension`](https://github.com/Supremeai-bd/supremeai-vscode/tree/main/extension)** | VS Code Extension (`.vsix`) | VS Code Marketplace / GitHub Releases |
| **[`/desktop`](https://github.com/Supremeai-bd/supremeai-vscode/tree/main/desktop)** | Windows / macOS / Linux Desktop App | GitHub Releases (`.exe`, `.dmg`, `.AppImage`) |
| **[`Supremeai-bd/supremeai-apk`](https://github.com/Supremeai-bd/supremeai-apk)** | Native Android App (Kotlin + Jetpack Compose) | Google Play Store / APK Releases |

> Satellite sovereignty (#4934): the `extension/` and `desktop/`
> sources live in the sovereign [`supremeai-vscode`](https://github.com/Supremeai-bd/supremeai-vscode)
> satellite repository; this hub keeps release docs and the root sentinel
> anchor (`package.json`) for zero-drift parity verification.

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
