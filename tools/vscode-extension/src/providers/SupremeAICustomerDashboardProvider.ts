import * as vscode from 'vscode';
import { getSupremeAIService } from '../services/SupremeAIService';
import { AuthService } from '../services/AuthService';

export class SupremeAICustomerDashboardProvider implements vscode.WebviewViewProvider {
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
    return '<!DOCTYPE html><html><body style="display:flex;justify-content:center;align-items:center;height:100vh;color:var(--vscode-descriptionForeground);font-family:sans-serif;"><div>🚀 Loading Customer Dashboard...</div></body></html>';
  }

  private setupWebviewMessageListener(webviewView: vscode.WebviewView): void {
    webviewView.webview.onDidReceiveMessage(
      async (data) => {
        switch (data.type) {
          case 'newChat':
            vscode.commands.executeCommand('supremeai.openChat');
            break;
          case 'logout':
            vscode.commands.executeCommand('supremeai.logout').then(() => {
              this.updateContent(webviewView);
            });
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
    const authService = AuthService.getInstance();
    const user = authService?.getUser();
    const username = user?.username || 'Guest User';
    const email = user?.email || 'N/A';

    return `<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="UTF-8">
  <style>
    :root {
      --glass-bg: rgba(255, 255, 255, 0.05);
      --glass-border: rgba(255, 255, 255, 0.1);
      --highlight: #10b981;
      --highlight-gradient: linear-gradient(135deg, #10b981 0%, #06b6d4 100%);
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
      box-shadow: 0 4px 15px rgba(16, 185, 129, 0.2);
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
    <h2>👤 User Dashboard</h2>
  </div>

  <div class="card">
    <div class="section-title">User Account</div>
    <div class="stat-row">
      <span class="stat-label">Username</span>
      <span class="stat-value">${username}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Email</span>
      <span class="stat-value" style="font-size: 10px;">${email}</span>
    </div>
  </div>

  <div class="card">
    <div class="section-title">Usage Statistics</div>
    <div class="stat-row">
      <span class="stat-label">Total Code Edits</span>
      <span class="stat-value">${stats?.editCount || 0}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Suggestions Accepted</span>
      <span class="stat-value">${stats?.feedbackCount || 0}</span>
    </div>
  </div>

  <div class="card">
    <div class="section-title">Quick Actions</div>
    <button class="btn" id="chatBtn">Open Chat Panel</button>
    <button class="btn" id="logoutBtn" style="background: transparent; border: 1px solid var(--glass-border); color: var(--vscode-foreground);">Logout</button>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    document.getElementById('chatBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'newChat' });
    });
    document.getElementById('logoutBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'logout' });
    });
  </script>
</body>
</html>`;
  }
}
