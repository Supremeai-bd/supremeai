# SupremeAI 2.0 Desktop Application

This is the Windows Desktop application for SupremeAI 2.0, built with Tauri and React.

## Overview

The SupremeAI Desktop Application provides a native Windows experience for interacting with the SupremeAI 2.0 platform, featuring:

- Native system tray integration
- Global keyboard shortcuts (Ctrl+Shift+S)
- Native notifications
- File system access
- Auto-update capabilities
- Offline support

## Project Structure

```
apps/desktop/
+-- src-tauri/          # Rust backend (Tauri)
¦   +-- src/
¦   ¦   +-- main.rs     # Main application logic
¦   +-- Cargo.toml      # Rust dependencies
¦   +-- tauri.conf.json # Tauri configuration
+-- src-ui/             # React frontend
¦   +-- src/
¦   ¦   +-- components/ # Reusable UI components
¦   ¦   +-- pages/      # Page components
¦   ¦   +-- services/   # API service definitions
¦   ¦   +-- stores/     # State management (Zustand)
¦   ¦   +-- App.tsx     # Root component
¦   ¦   +-- main.tsx    # Entry point
¦   +-- package.json    # NPM dependencies
¦   +-- tsconfig.json   # TypeScript configuration
¦   +-- vite.config.ts  # Vite configuration
+-- wix/                # Windows Installer (WiX) files
+-- package.json        # Workspace configuration
+README.md              # This file
```

## Development

### Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Rust](https://www.rust-lang.org/) (stable)
- [Tauri CLI](https://tauri.app/v1/guides/getting-started/prerequisites)

### Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

This will start both the Vite dev server and the Tauri application.

### Building for Production

```bash
npm run build
```

This will create a production-ready Windows installer in `src-tauri/target/release/bundle/msi/`.

## Features Implemented

- Basic window with system tray
- Global keyboard shortcut (Ctrl+Shift+S)
- Native notifications
- File system access
- HTTP client for API communication
- Basic React UI structure

## Next Steps

1. Implement actual API integration with SupremeAI backend
2. Add authentication flows
3. Implement chat interface with real AI responses
4. Add skills marketplace integration
5. Implement system tray with quick actions
6. Add auto-update functionality
7. Code signing for production distribution

## License

MIT

