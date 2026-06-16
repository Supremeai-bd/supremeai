/**
 * SupremeAI VS Code Extension - Main Entry Point
 * Real-time learning and AI assistance integration
 */

import * as vscode from 'vscode';
import { SupremeAIService, setSupremeAIService } from './services/SupremeAIService';
import { AuthService } from './services/AuthService';
import { CodeEditHandler } from './handlers/CodeEditHandler';
import { ErrorHandler } from './handlers/ErrorHandler';
import { FeedbackHandler } from './handlers/FeedbackHandler';
import { CodeFlowHandler, setCodeFlowHandler } from './handlers/CodeFlowHandler';
import { SupremeAIConfig } from './types';
import { SupremeAISidebarProvider } from './providers/SupremeAISidebarProvider';
import { SupremeAIActivityProvider } from './providers/SupremeAIActivityProvider';
import { SupremeAIChatProvider } from './providers/SupremeAIChatProvider';
import { AIService, getAIService, setAIService } from './ai/AIService';
import { CodeGenerationService, getCodeGenerationService, setCodeGenerationService } from './ai/CodeGenerationService';
import { CodeReviewService, getCodeReviewService, setCodeReviewService } from './ai/CodeReviewService';
import { detectOtherAiAgents } from './agentDetector'; // এজেন্ট ডিটেক্টর ইম্পোর্ট করা হলো

let currentBrowserPreviewPanel: vscode.WebviewPanel | undefined; // ব্রাউজার প্রিভিউ প্যানেল ট্র্যাক করার জন্য
let supremeAIService: SupremeAIService;
let aiService: AIService;
let codeGenService: CodeGenerationService;
let codeReviewService: CodeReviewService;
let codeFlowHandler: CodeFlowHandler;

export async function activate(context: vscode.ExtensionContext) {
  console.log('[SupremeAI] VS Code Extension activating...');

  const config = vscode.workspace.getConfiguration('supremeai');
  const backendUrl = config.get<string>('backendUrl', 'https://supremeai-a.web.app');

  const supremeConfig: SupremeAIConfig = {
    backendUrl,
    enableRealTimeLearning: config.get<boolean>('enableRealTimeLearning', true),
    autoReportErrors: config.get<boolean>('autoReportErrors', true),
  };

  supremeAIService = new SupremeAIService(supremeConfig);
  setSupremeAIService(supremeAIService);

  const auth = AuthService.getInstance(supremeConfig);
  await auth.loginAsGuest();

  // Register URI handler for OAuth callback
  const authSuccessDisposable = vscode.window.registerUriHandler({
    handleUri: async (uri: vscode.Uri) => {
      console.log('[SupremeAI] URI callback received:', uri.toString());
      
      if (uri.query.includes('action=login') || uri.path.includes('callback')) {
        const params = new URLSearchParams(uri.query);
        const token = params.get('token');
        const userParam = params.get('user');
        
        if (token) {
          const auth = AuthService.getInstance();
          if (auth) {
            auth.setToken(token);
            if (userParam) {
              try {
                auth.setUser(JSON.parse(decodeURIComponent(userParam)));
              } catch {
                auth.setUser({ username: 'User' });
              }
            }
            vscode.window.showInformationMessage('Login successful! Welcome to SupremeAI.');
          }
        }
      }
    }
  });
  context.subscriptions.push(authSuccessDisposable);

  aiService = getAIService();
  setAIService(aiService);

  // প্রো-টিপ: ইউজারের প্রাইভেসি নিশ্চিত করতে লোকাল স্ট্যাটিসটিক্স মুছে ফেলা হচ্ছে
  context.globalState.update('patternsLearned', undefined);
  context.globalState.update('codeEdits', undefined);
  context.globalState.update('errorsReported', undefined);
  context.globalState.update('feedbackGiven', undefined);

  // লার্নিং এর অংশ হিসেবে অন্য এআই এজেন্ট ডিটেক্ট করা এবং রিপোর্ট করা
  const agents = detectOtherAiAgents();
  if (agents.length > 0) {
    supremeAIService.sendCodeAnalysis('env-discovery', `Detected AI Agents in environment: ${agents.join(', ')}`, 'system-meta');

    // প্রতিটি ডিটেক্ট করা এজেন্টকে PROPOSED হিসেবে ব্যাকএন্ডে পাঠানো
    agents.forEach(agentName => {
      supremeAIService.registerProposedFeature({
        id: `ext-agent-${agentName.toLowerCase().replace(/\s+/g, '-')}`,
        name: agentName,
        category: 'EXTERNAL_AI_AGENT',
        provider: 'Detected on Host',
        status: 'PROPOSED', // অ্যাডমিন পরে এটি ACTIVE করতে পারবেন
        description: `This agent was detected running on the user's VS Code environment.`
      });
    });
  }

  codeGenService = new CodeGenerationService();
  setCodeGenerationService(codeGenService);

  codeReviewService = new CodeReviewService();
  setCodeReviewService(codeReviewService);

  const editHandler = new CodeEditHandler(context);
  const errHandler = new ErrorHandler(context);
  const fbHandler = new FeedbackHandler(context);
  codeFlowHandler = new CodeFlowHandler(context);
  setCodeFlowHandler(codeFlowHandler);

  editHandler.register();
  errHandler.register();
  fbHandler.register();
  codeFlowHandler.register();

  // হেল্পার ফাংশন: বর্তমান প্রজেক্টের কন্টেক্সট (Language/Framework) সংগ্রহ করা
  async function getProjectContext(): Promise<string> {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders) return "No workspace context";

    // ফাইল চেক করে ফ্রেমওয়ার্ক ডিটেক্ট করা
    const packageJson = await vscode.workspace.findFiles('package.json', null, 1);
    const buildGradle = await vscode.workspace.findFiles('build.gradle', null, 1);

    let context = "Context: ";
    if (packageJson.length) context += "React/Node.js Project. ";
    if (buildGradle.length) context += "Java Spring Boot Project. ";

    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor) {
      context += `Current File: ${activeEditor.document.fileName} (${activeEditor.document.languageId})`;
    }
    return context;
  }

  // প্রো-টিপ: ব্রাউজার অটোমেশনের লাইভ প্রিভিউ দেখানোর জন্য একটি ওয়েবভিউ প্যানেল তৈরি করা
  function createBrowserPreviewPanel(context: vscode.ExtensionContext, title: string, sessionId: string): vscode.WebviewPanel {
    if (currentBrowserPreviewPanel) {
      currentBrowserPreviewPanel.dispose(); // যদি কোনো প্যানেল খোলা থাকে, সেটি বন্ধ করুন
    }

    const panel = vscode.window.createWebviewPanel(
      'supremeaiBrowserPreview', // ইন্টারনাল প্যানেল আইডি
      title, // ইউজারের কাছে প্রদর্শিত টাইটেল
      vscode.ViewColumn.Beside, // সক্রিয় এডিটর এর পাশে একটি নতুন কলামে দেখান
      {
        enableScripts: true, // ওয়েবভিউতে জাভাস্ক্রিপ্ট সক্ষম করুন
        retainContextWhenHidden: true, // লুকানো থাকলেও ওয়েবভিউ সচল রাখুন
      }
    );

    currentBrowserPreviewPanel = panel;

    panel.webview.html = getWebviewContent(sessionId);

    // ওয়েবভিউ থেকে আসা মেসেজ হ্যান্ডেল করুন
    panel.webview.onDidReceiveMessage(
      message => {
        switch (message.command) {
          case 'stop':
            vscode.window.showInformationMessage(`ব্রাউজার টাস্ক ${sessionId} বন্ধ করা হচ্ছে।`);
            // TODO: supremeAIService এর মাধ্যমে ব্যাকএন্ডে স্টপ কমান্ড পাঠান
            return;
          case 'pause':
            vscode.window.showInformationMessage(`ব্রাউজার টাস্ক ${sessionId} পজ করা হচ্ছে।`);
            // TODO: supremeAIService এর মাধ্যমে ব্যাকএন্ডে পজ কমান্ড পাঠান
            return;
          case 'resume':
            vscode.window.showInformationMessage(`ব্রাউজার টাস্ক ${sessionId} চালু করা হচ্ছে।`);
            // TODO: supremeAIService এর মাধ্যমে ব্যাকএন্ডে রিজুম কমান্ড পাঠান
            return;
          // ইউজারের ইন্টারঅ্যাকশনের জন্য আরও কমান্ড যোগ করুন (যেমন: ক্লিক কোঅর্ডিনেটস)
        }
      },
      undefined,
      context.subscriptions
    );

    // প্যানেল বন্ধ হলে ক্লিনআপ করুন
    panel.onDidDispose(() => {
      currentBrowserPreviewPanel = undefined;
      // TODO: এই সেশনের জন্য স্ট্রিমিং বন্ধ করতে ব্যাকএন্ডকে জানান
    }, null, context.subscriptions);

    return panel;
  }

  function getWebviewContent(sessionId: string): string {
    // এটি একটি মৌলিক HTML কাঠামো। একটি বাস্তব অ্যাপে, আপনি এখানে আরও জটিল React/Vue অ্যাপ লোড করবেন।
    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SupremeAI ব্রাউজার প্রিভিউ</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 10px; background-color: var(--vscode-editor-background); color: var(--vscode-editor-foreground); }
        #controls { margin-bottom: 10px; display: flex; gap: 10px; }
        #previewContainer { position: relative; display: inline-block; }
        #previewImage { max-width: 100%; height: auto; border: 1px solid var(--vscode-editorGroup-border); cursor: crosshair; }
        #logOutput { background-color: var(--vscode-editorWidget-background); border: 1px solid var(--vscode-editorGroup-border); padding: 10px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 0.9em; }
        button { background-color: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 8px 12px; cursor: pointer; border-radius: 3px; }
        button:hover { background-color: var(--vscode-button-hoverBackground); }
        #interactionBox { margin-top: 10px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; display: none; }
        #interactionBox.active { display: block; border: 2px solid var(--vscode-button-background); }
        input { background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); padding: 5px; width: 70%; }
    </style>
</head>
<body>
    <h1>Godmode 3 লাইভ প্রিভিউ (Session: ${sessionId})</h1>
    <div id="controls">
        <button id="stopButton">বন্ধ করুন</button>
        <button id="pauseButton">পজ করুন</button>
        <button id="resumeButton">চালু করুন</button>
    </div>
    <div id="previewContainer">
        <img id="previewImage" src="" alt="লাইভ ব্রাউজার প্রিভিউ" />
    </div>
    <div id="interactionBox">
        <p id="promptText">AI আপনার সাহায্য চাইছে...</p>
        <input type="text" id="userInput" placeholder="এখানে ইনপুট দিন..." />
        <button id="sendInput">পাঠান</button>
    </div>
    <h2>লগ আউটপুট</h2>
    <div id="logOutput"></div>

    <script>
        const vscode = acquireVsCodeApi();
        const previewImage = document.getElementById('previewImage');
        const logOutput = document.getElementById('logOutput');
        const stopButton = document.getElementById('stopButton');
        const pauseButton = document.getElementById('pauseButton');
        const resumeButton = document.getElementById('resumeButton');
        const interactionBox = document.getElementById('interactionBox');
        const userInput = document.getElementById('userInput');
        const sendInput = document.getElementById('sendInput');
        const promptText = document.getElementById('promptText');

        stopButton.addEventListener('click', () => {
            vscode.postMessage({ command: 'stop', sessionId: '${sessionId}' });
        });
        pauseButton.addEventListener('click', () => {
            vscode.postMessage({ command: 'pause', sessionId: '${sessionId}' });
        });
        resumeButton.addEventListener('click', () => {
            vscode.postMessage({ command: 'resume', sessionId: '${sessionId}' });
        });

        previewImage.addEventListener('click', (e) => {
            const rect = previewImage.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;
            vscode.postMessage({ command: 'click', sessionId: '${sessionId}', x, y });
        });

        sendInput.addEventListener('click', () => {
            const text = userInput.value;
            if (text) {
                vscode.postMessage({ command: 'userInput', sessionId: '${sessionId}', text });
                userInput.value = '';
                interactionBox.classList.remove('active');
            }
        });

        window.addEventListener('message', event => {
            const message = event.data; // The JSON data our extension sent
            switch (message.type) {
                case 'updateImage':
                    previewImage.src = 'data:image/png;base64,' + message.data;
                    break;
                case 'updateLog':
                    logOutput.innerHTML += \`<p>\${message.data}</p>\`;
                    logOutput.scrollTop = logOutput.scrollHeight; // Scroll to bottom
                    break;
                case 'askUser':
                    promptText.innerText = message.data;
                    interactionBox.classList.add('active');
                    userInput.focus();
                    break;
                case 'taskComplete':
                    logOutput.innerHTML += \`<p><b>টাস্ক সম্পন্ন হয়েছে:</b> \${message.result}</p>\`;
                    vscode.window.showInformationMessage('ব্রাউজার টাস্ক সম্পন্ন হয়েছে!');
                    break;
            }
        });
    </script>
</body>
</html>`;
  }

  // ইউজারের জন্য শুধুমাত্র চ্যাট ট্যাব রাখা হচ্ছে, বাকিগুলো অ্যাডমিন ড্যাশবোর্ডের জন্য
  // registerSidebarViews(context); // ড্যাশবোর্ড এবং কোড ফ্লো ভিউ সরানো হলো
  // registerActivityView(context); // অ্যাক্টিভিটি ভিউ সরানো হলো
  registerChatProvider(context);
  registerInlineCompletionProvider(context, fbHandler);

  registerCommands(context);
  registerStatusBar(context);

  // নতুন কমান্ড: স্ট্যাটাস বার ক্লিক করলে চ্যাট ট্যাব খোলার জন্য
  context.subscriptions.push(
    vscode.commands.registerCommand('supremeai.openChat', () => {
      vscode.commands.executeCommand('workbench.view.extension.supremeaiChat');
    })
  );

  vscode.window.showInformationMessage(
    'SupremeAI Real-Time Learning is active!',
    'Settings'
  ).then(selection => {
    if (selection === 'Settings') {
      vscode.commands.executeCommand('workbench.action.openSettings', 'supremeai');
    }
  });

  console.log('[SupremeAI] Extension fully activated');
}

function registerCommands(context: vscode.ExtensionContext): void {
  const forceLearnCommand = vscode.commands.registerCommand('supremeai.forceLearn', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('No active editor to learn from');
      return;
    }

    const document = editor.document;
    const code = document.getText();
    const language = document.languageId;

    try {
      await supremeAIService.sendCodeAnalysis(document.fileName, code, language);
      vscode.window.showInformationMessage('Code analysis sent for learning');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      vscode.window.showErrorMessage(`Failed to send code analysis: ${message}`);
    }
  });

  const explainCodeCommand = vscode.commands.registerCommand('supremeai.explainCode', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('No active editor selected.');
      return;
    }
    const selection = editor.selection;
    const text = selection.isEmpty ? editor.document.getText() : editor.document.getText(selection);
    if (!text.trim()) {
      vscode.window.showWarningMessage('No code selected to explain.');
      return;
    }
    
    vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: "Explaining Code...",
      cancellable: false
    }, async () => {
      try {
        const response = await supremeAIService.sendChatMessage({
          message: `Please explain the following code in detail:\n\n\`\`\`${editor.document.languageId}\n${text}\n\`\`\``
        });
        const panel = vscode.window.createWebviewPanel(
          'supremeaiExplanation',
          'Code Explanation',
          vscode.ViewColumn.Two,
          {}
        );
        panel.webview.html = `<html><body><pre style="white-space: pre-wrap; font-family: sans-serif; padding: 15px;">${response.reply}</pre></body></html>`;
      } catch (error) {
        vscode.window.showErrorMessage(`Failed to explain code: ${error}`);
      }
    });
  });

  const reviewCodeCommand = vscode.commands.registerCommand('supremeai.reviewCode', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('No active editor selected.');
      return;
    }
    const selection = editor.selection;
    const text = selection.isEmpty ? editor.document.getText() : editor.document.getText(selection);
    if (!text.trim()) {
      vscode.window.showWarningMessage('No code selected to review.');
      return;
    }
    
    vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: "Reviewing Code...",
      cancellable: false
    }, async () => {
      try {
        const response = await supremeAIService.sendChatMessage({
          message: `Please review the following code for bugs, style issues, and performance optimizations:\n\n\`\`\`${editor.document.languageId}\n${text}\n\`\`\``
        });
        const panel = vscode.window.createWebviewPanel(
          'supremeaiReview',
          'Code Review',
          vscode.ViewColumn.Two,
          {}
        );
        panel.webview.html = `<html><body><pre style="white-space: pre-wrap; font-family: sans-serif; padding: 15px;">${response.reply}</pre></body></html>`;
      } catch (error) {
        vscode.window.showErrorMessage(`Failed to review code: ${error}`);
      }
    });
  });

  const loginAsGuestCommand = vscode.commands.registerCommand('supremeai.loginAsGuest', async () => {
    const auth = AuthService.getInstance();
    if (auth) {
      await auth.loginAsGuest();
    }
  });

  const loginCommand = vscode.commands.registerCommand('supremeai.login', async () => {
    const auth = AuthService.getInstance();
    if (auth) {
      await auth.login();
    }
  });

  const logoutCommand = vscode.commands.registerCommand('supremeai.logout', async () => {
    const auth = AuthService.getInstance();
    if (auth) {
      await auth.logout();
    }
  });

  context.subscriptions.push(
    forceLearnCommand,
    explainCodeCommand,
    reviewCodeCommand,
    loginAsGuestCommand,
    loginCommand,
    logoutCommand
  );
}

function registerSidebarViews(context: vscode.ExtensionContext): void {
  const dashboardProvider = new SupremeAISidebarProvider(context.extensionUri, 'supremeaiDashboard');
  const codeFlowProvider = new SupremeAISidebarProvider(context.extensionUri, 'supremeaiCodeFlow');

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('supremeaiDashboard', dashboardProvider),
    vscode.window.registerWebviewViewProvider('supremeaiCodeFlow', codeFlowProvider)
  );
}

function registerChatProvider(context: vscode.ExtensionContext): void {
  const chatProvider = new SupremeAIChatProvider(context);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('supremeaiChat', chatProvider)
  );
}

function registerActivityView(context: vscode.ExtensionContext): void {
  const activityProvider = new SupremeAIActivityProvider();
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('supremeaiActivity', activityProvider)
  );
}

function registerStatusBar(context: vscode.ExtensionContext): void {
  const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.text = '$(brain) SupremeAI';
  statusBarItem.tooltip = 'SupremeAI Assistant (Chat)';
  statusBarItem.command = 'supremeai.openChat'; // স্ট্যাটাস বার ক্লিক করলে চ্যাট ট্যাব খুলবে
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);
}

function registerInlineCompletionProvider(context: vscode.ExtensionContext, fbHandler: FeedbackHandler): void {
  let debounceTimeout: NodeJS.Timeout | undefined;

  const provider: vscode.InlineCompletionItemProvider = {
    async provideInlineCompletionItems(
      document: vscode.TextDocument,
      position: vscode.Position,
      context: vscode.InlineCompletionContext,
      token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionList | vscode.InlineCompletionItem[] | undefined> {
      
      const config = vscode.workspace.getConfiguration('supremeai');
      const enableRealTimeLearning = config.get<boolean>('enableRealTimeLearning', true);
      if (!enableRealTimeLearning) {
        return undefined;
      }

      if (debounceTimeout) {
        clearTimeout(debounceTimeout);
      }

      return new Promise<vscode.InlineCompletionList | undefined>((resolve) => {
        debounceTimeout = setTimeout(async () => {
          if (token.isCancellationRequested) {
            resolve(undefined);
            return;
          }

          try {
            const docText = document.getText();
            const offset = document.offsetAt(position);
            const prefix = docText.substring(0, offset);
            const suffix = docText.substring(offset);

            const response = await supremeAIService.getInlineCompletions(
              prefix,
              suffix,
              document.fileName,
              document.languageId
            );

            if (token.isCancellationRequested) {
              resolve(undefined);
              return;
            }

            if (!response.suggestions || response.suggestions.length === 0) {
              resolve(undefined);
              return;
            }

            const items: vscode.InlineCompletionItem[] = response.suggestions.map((text) => {
              const item = new vscode.InlineCompletionItem(text);
              const suggestionId = `inline-${Date.now()}`;
              
              fbHandler.captureSuggestionContext(
                suggestionId,
                `completion-${Date.now()}`,
                "", 
                text,
                `File: ${document.uri.fsPath}`
              );

              item.command = {
                title: 'Accept Suggestion',
                command: 'supremeai.acceptSuggestion',
                arguments: [document.fileName, text, document.languageId]
              };
              return item;
            });

            resolve({ items });
          } catch (error) {
            console.error('[SupremeAI] Error fetching inline completion:', error);
            resolve(undefined);
          }
        }, 400); // 400ms debounce
      });
    }
  };

  const disposable = vscode.languages.registerInlineCompletionItemProvider(
    { pattern: '**' },
    provider
  );
  context.subscriptions.push(disposable);
  console.log('[SupremeAI] InlineCompletionItemProvider registered');
}

export function deactivate() {
  console.log('[SupremeAI] VS Code Extension deactivating...');
}