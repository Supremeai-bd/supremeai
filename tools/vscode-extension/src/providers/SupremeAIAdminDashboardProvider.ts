// ============================================================================
// file >> SupremeAIAdminDashboardProvider.ts
// project >> SupremeAI 2.0
// purpose >> Admin panel and controls
// module >> tools
// ============================================================================
import { getSupremeAIService } from '../services/SupremeAIService';
import { AuthService } from '../services/AuthService';

export class SupremeAIAdminDashboardProvider implements vscode.WebviewViewProvider {
  private webview: vscode.WebviewView | null = null;
  private updateTimer: NodeJS.Timeout | null = null;

  constructor(
    private readonly _extensionUri: vscode.Uri
  ) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this.webview = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    this.setupWebviewMessageListener(webviewView);
    webviewView.webview.html = this.getLoadingHTML();
    
    this.updateContent(webviewView);
    this.startPeriodicUpdates();
  }

  private getLoadingHTML(): string {
    return '<!DOCTYPE html><html><body style="display:flex;justify-content:center;align-items:center;height:100vh;color:var(--vscode-descriptionForeground);font-family:sans-serif;"><div>🚀 Loading Admin Dashboard...</div></body></html>';
  }

  private setupWebviewMessageListener(webviewView: vscode.WebviewView): void {
    webviewView.webview.onDidReceiveMessage(
      async (data) => {
        switch (data.type) {
          case 'analyzeCodeFlow':
            vscode.commands.executeCommand('supremeai.analyzeCodeFlow');
            break;
          case 'runSecurityAudit':
            vscode.commands.executeCommand('supremeai.sendMessageToChat', 'Please run a security audit on my current active codebase.');
            break;
          case 'openSettings':
            vscode.commands.executeCommand('workbench.action.openSettings', 'supremeai');
            break;
          case 'refresh':
            this.updateContent(webviewView);
            break;
        }
      },
      undefined
    );
  }

  private async updateContent(webviewView: vscode.WebviewView): Promise<void> {
    const service = getSupremeAIService();
    const stats = await service.getLearningStats();
    webviewView.webview.html = this.getHTMLContent(stats);
  }

  private startPeriodicUpdates(): void {
    this.updateTimer = setInterval(() => {
      if (this.webview) {
        this.updateContent(this.webview);
      }
    }, 15000); // 15 seconds refresh
  }

  public dispose(): void {
    if (this.updateTimer) {
      clearInterval(this.updateTimer);
      this.updateTimer = null;
    }
    this.webview = null;
  }

  private getHTMLContent(stats: any): string {
    const config = vscode.workspace.getConfiguration('supremeai');
    const apiProvider = config.get<string>('apiProvider') || 'openrouter';
    const model = config.get<string>('aiModel') || 'openrouter/anthropic/claude-3.5-sonnet';

    return `<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="UTF-8">
  <style>
    :root {
      --glass-bg: rgba(255, 255, 255, 0.05);
      --glass-border: rgba(255, 255, 255, 0.1);
      --highlight: #a855f7;
      --highlight-gradient: linear-gradient(135deg, #a855f7 0%, #6366f1 100%);
    }
    body {
      font-family: var(--vscode-font-family, sans-serif);
      padding: 12px;
      color: var(--vscode-foreground);
      background-color: var(--vscode-sideBar-background);
      margin: 0;
    }
    .card {
      background: var(--glass-bg);
      border: 1px solid var(--glass-border);
      backdrop-filter: blur(10px);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 12px;
    }
    .header {
      background: var(--highlight-gradient);
      color: white;
      padding: 14px;
      border-radius: 8px;
      margin-bottom: 16px;
      text-align: center;
      box-shadow: 0 4px 15px rgba(168, 85, 247, 0.2);
    }
    .header h2 {
      margin: 0;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    .stat-row {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid var(--glass-border);
      font-size: 12px;
    }
    .stat-label {
      color: var(--vscode-descriptionForeground);
    }
    .stat-value {
      font-weight: bold;
      color: var(--highlight);
    }
    .btn {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      width: 100%;
      margin-top: 8px;
      font-weight: bold;
      font-size: 12px;
      transition: background 0.2s ease;
    }
    .btn:hover {
      background: var(--vscode-button-hoverBackground);
    }
    .section-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 8px;
      font-weight: 700;
    }
  </style>
</head>
<body>
  <div class="header">
    <h2>🔱 Admin Dashboard</h2>
  </div>

  <div class="card">
    <div class="section-title">System Status</div>
    <div class="stat-row">
      <span class="stat-label">Active Provider</span>
      <span class="stat-value" style="text-transform: uppercase;">${apiProvider}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Model</span>
      <span class="stat-value" style="font-size: 10px;">${model}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Auto-Learn</span>
      <span class="stat-value">${stats?.enabled ? '✅ Active' : '❌ Inactive'}</span>
    </div>
  </div>

  <div class="card">
    <div class="section-title">Admin Controls</div>
    <button class="btn" id="analyzeBtn">Run CodeFlow Analysis</button>
    <button class="btn" id="securityAuditBtn">Run Security Audit via Chat</button>
    <button class="btn" id="settingsBtn" style="background: transparent; border: 1px solid var(--glass-border); color: var(--vscode-foreground);">Settings</button>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    document.getElementById('analyzeBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'analyzeCodeFlow' });
    });
    document.getElementById('securityAuditBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'runSecurityAudit' });
    });
    document.getElementById('settingsBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'openSettings' });
    });
  </script>
</body>
</html>`;
  }
}
