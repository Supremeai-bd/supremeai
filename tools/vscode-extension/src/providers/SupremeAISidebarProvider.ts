// ============================================================================
// file >> SupremeAISidebarProvider.ts
// project >> SupremeAI 2.0
// purpose >> VS Code providers
// module >> tools
// ============================================================================
import { getSupremeAIService } from '../services/SupremeAIService';
import { AuthService } from '../services/AuthService';

export class SupremeAISidebarProvider implements vscode.WebviewViewProvider {
  private webview: vscode.WebviewView | null = null;
  private updateTimer: NodeJS.Timeout | null = null;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly _viewId: string
  ) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this.webview = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    this.setupWebviewMessageListener(webviewView);
    
    // Set initial loading state to avoid blank screen
    webviewView.webview.html = this.getLoadingHTML();
    
    this.updateContent(webviewView);
    this.startPeriodicUpdates();
  }

  private getLoadingHTML(): string {
    return '<!DOCTYPE html><html><body style="display:flex;justify-content:center;align-items:center;height:100vh;color:var(--vscode-descriptionForeground);font-family:sans-serif;"><div>🚀 Loading SupremeAI...</div></body></html>';
  }

  private setupWebviewMessageListener(webviewView: vscode.WebviewView): void {
    webviewView.webview.onDidReceiveMessage(
      async (data) => {
        switch (data.type) {
          case 'forceLearn':
            await this.handleForceLearn();
            break;
          case 'login':
            vscode.commands.executeCommand('supremeai.login').then(() => {
              this.updateContent(webviewView);
            });
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

  private async handleForceLearn(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('No active editor to learn from');
      return;
    }

    const filePath = editor.document.uri.fsPath;
    const code = editor.document.getText();

    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'SupremeAI Learning',
        cancellable: false,
      },
      async (progress) => {
        progress.report({ increment: 0, message: 'Analyzing code...' });
        const service = getSupremeAIService();
        const result = await service.sendCodeAnalysis(filePath, code, editor.document.languageId);
        progress.report({ increment: 100, message: 'Complete!' });

        if (result.success) {
          vscode.window.showInformationMessage('✅ Code analysis sent to SupremeAI learning engine');
          this.updateContent(this.webview!);
        } else {
          vscode.window.showErrorMessage(`❌ Learning failed: ${result.message}`);
        }
      }
    );
  }

  private async updateContent(webviewView: vscode.WebviewView): Promise<void> {
    const authService = AuthService.getInstance();
    if (!authService || !authService.isAuthenticated()) {
      webviewView.webview.html = this.getLoginHTML();
      return;
    }

    const service = getSupremeAIService();
    const stats = await service.getLearningStats();

    const content = this.getHTMLContent(stats);
    webviewView.webview.html = content;
  }

  private getLoginHTML(): string {
    return `<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="UTF-8">
  <style>
    body {
      font-family: var(--vscode-font-family);
      padding: 20px;
      color: var(--vscode-foreground);
      background-color: var(--vscode-sideBar-background);
      text-align: center;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      height: 80vh;
    }
    .logo {
      font-size: 50px;
      margin-bottom: 20px;
    }
    .title {
      font-size: 18px;
      font-weight: bold;
      margin-bottom: 10px;
    }
    .desc {
      font-size: 13px;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 24px;
      line-height: 1.5;
    }
    .btn {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 10px 20px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      font-weight: bold;
      width: 100%;
      max-width: 200px;
    }
    .btn:hover {
      background: var(--vscode-button-hoverBackground);
    }
  </style>
</head>
<body>
  <div class="logo">🤖</div>
  <div class="title">SupremeAI-তে লগইন করুন</div>
  <div class="desc">আপনার কোড অ্যাসিস্ট্যান্ট ব্যবহার করতে এবং রিয়েল-টাইম এআই মেমোরি সিঙ্ক চালু করতে সাইন-ইন করা প্রয়োজন।</div>
  <button class="btn" id="loginBtn">লগইন করুন</button>

  <script>
    const vscode = acquireVsCodeApi();
    document.getElementById('loginBtn').addEventListener('click', () => {
      vscode.postMessage({ type: 'login' });
    });
  </script>
</body>
</html>`;
  }

  private startPeriodicUpdates(): void {
    this.updateTimer = setInterval(() => {
      if (this.webview) {
        this.updateContent(this.webview);
      }
    }, 30000); // Update every 30 seconds
  }

  public dispose(): void {
    if (this.updateTimer) {
      clearInterval(this.updateTimer);
      this.updateTimer = null;
    }
    this.webview = null;
  }

  private getHTMLContent(stats: any): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: var(--vscode-font-family);
      padding: 10px;
      color: var(--vscode-foreground);
      background-color: var(--vscode-sideBar-background);
    }
    .header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }
    .icon {
      font-size: 24px;
    }
    .title {
      font-size: 16px;
      font-weight: bold;
      margin: 0;
    }
    .section {
      margin-bottom: 16px;
    }
    .section-title {
      font-size: 12px;
      text-transform: uppercase;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 8px;
      font-weight: 600;
    }
    .stat-item {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid var(--vscode-sideBarSectionHeader-border);
    }
    .stat-label {
      color: var(--vscode-descriptionForeground);
    }
    .stat-value {
      font-weight: bold;
      color: var(--vscode-foreground);
    }
    .button {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      width: 100%;
      margin: 4px 0;
      font-size: 13px;
    }
    .button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    .status {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: bold;
    }
    .status.active {
      background: var(--vscode-testing-iconPassed);
      color: white;
    }
    .status.inactive {
      background: var(--vscode-errorBackground);
      color: white;
    }
    .activity-item {
      padding: 8px;
      margin: 4px 0;
      background: var(--vscode-list-hoverBackground);
      border-radius: 4px;
      font-size: 12px;
    }
    .empty-state {
      color: var(--vscode-descriptionForeground);
      text-align: center;
      padding: 20px;
      font-style: italic;
    }
  </style>
</head>
<body>
  <div class="header">
    <span class="icon">$(circuit-board)</span>
    <span class="title">SupremeAI</span>
    <span class="status ${stats?.enabled ? 'active' : 'inactive'}">${stats?.enabled ? 'Active' : 'Disabled'}</span>
  </div>

  <div class="section">
    <div class="section-title">Learning Statistics</div>
    <div class="stat-item">
      <span class="stat-label">Patterns Learned</span>
      <span class="stat-value">${stats?.learningCount || 0}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Code Edits</span>
      <span class="stat-value">${stats?.editCount || 0}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Errors Reported</span>
      <span class="stat-value">${stats?.errorCount || 0}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Feedback Given</span>
      <span class="stat-value">${stats?.feedbackCount || 0}</span>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Actions</div>
    <button class="button" id="forceLearn">$(sync) Force Learn Current File</button>
    <button class="button" id="reportError">$(error) Report Error</button>
    <button class="button" id="sendFeedback">$(comment) Send Feedback</button>
    <button class="button" id="openSettings">$(settings) Settings</button>
  </div>

  <div class="section">
    <div class="section-title">Recent Activity</div>
    <div id="activity">
      ${this.renderActivity(stats)}
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();

    document.getElementById('forceLearn').addEventListener('click', () => {
      vscode.postMessage({ type: 'forceLearn' });
    });

    document.getElementById('reportError').addEventListener('click', () => {
      vscode.postMessage({ type: 'reportError' });
    });

    document.getElementById('sendFeedback').addEventListener('click', () => {
      vscode.postMessage({ type: 'sendFeedback' });
    });

    document.getElementById('openSettings').addEventListener('click', () => {
      vscode.postMessage({ type: 'openSettings' });
    });
  </script>
</body>
</html>`;
  }

  private renderActivity(stats: any): string {
    if (!stats?.recentActivity || stats.recentActivity.length === 0) {
      return '<div class="empty-state">No recent activity</div>';
    }

    return stats.recentActivity
      .map((activity: any) => {
        const icon = this.getActivityIcon(activity.type);
        const time = this.formatTime(activity.timestamp);
        return `<div class="activity-item">
          <span>${icon}</span> ${activity.message} • ${time}
        </div>`;
      })
      .join('');
  }

  private getActivityIcon(type: string): string {
    switch (type) {
      case 'CODE_EDIT': return '$(edit)';
      case 'ERROR_REPORT': return '$(error)';
      case 'SUGGESTION_FEEDBACK': return '$(thumbsup)';
      default: return '$(info)';
    }
  }

  private formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);

    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m`;
    if (hours < 24) return `${hours}h`;
    return date.toLocaleDateString();
  }
}
