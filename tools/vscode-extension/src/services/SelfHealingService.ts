import * as vscode from 'vscode';
import { SupremeAIService } from './SupremeAIService';
import { HealingStateManager, HealingState } from './HealingStateManager';
import { BaseDisposable } from '../utils/BaseDisposable';
import { TelemetryTracker } from './TelemetryTracker';

export class SelfHealingService extends BaseDisposable {
    private static instance: SelfHealingService;
    private supremeService: SupremeAIService;
    private debounceTimer: NodeJS.Timeout | null = null;
    private isHealing = false;

    private constructor(supremeService: SupremeAIService) {
        super();
        this.supremeService = supremeService;
    }

    public static initialize(context: vscode.ExtensionContext, supremeService: SupremeAIService): SelfHealingService {
        if (!this.instance) {
            this.instance = new SelfHealingService(supremeService);
            this.instance.registerListeners(context);
            context.subscriptions.push(this.instance);
            console.log('🩺 [Self-Healing] Agent-in-the-Loop initialized.');
        }
        return this.instance;
    }

    private registerListeners(context: vscode.ExtensionContext) {
        // Performance optimization: Automatic diagnostic listening disabled to prevent high CPU/RAM usage while typing.
        // Self-healing is triggered manually via QuickFix CodeAction or user request.
    }

    private handleDiagnosticsChange(uris: readonly vscode.Uri[]) {
        // Disabled automatic background scanning for zero-lag editing.
    }

    private async processDiagnostics(uris: readonly vscode.Uri[]) {
        // Find the first active text editor with errors
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;

        const uri = editor.document.uri;
        if (!uris.some(u => u.toString() === uri.toString())) return;

        const diagnostics = vscode.languages.getDiagnostics(uri);
        const errors = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Error);

        if (errors.length === 0) return;

        // Process only the first error for now
        const primaryError = errors[0];
        const stateManager = HealingStateManager.getInstance();

        stateManager.setState(HealingState.ANALYZING_ERROR);

        // Gather Context
        const line = primaryError.range.start.line;
        const semanticContext = await getSemanticContext(editor.document, line);

        const payload = {
            filePath: uri.fsPath,
            message: primaryError.message,
            lineNumber: line + 1,
            codeContext: semanticContext,
            languageId: editor.document.languageId
        };

        this.isHealing = true;
        stateManager.setState(HealingState.GENERATING_PATCH);

        try {
            const fixResponse = await this.supremeService.requestSelfHealing(payload);

            if (fixResponse && fixResponse.fixedCode) {
                stateManager.setState(HealingState.APPLYING_DIFF);

                // Track for Telemetry
                TelemetryTracker.trackProposedPatch(uri.fsPath, `error-${Date.now()}`, fixResponse.fixedCode);

                await this.showDiffView(uri, editor.document.getText(), fixResponse.fixedCode);
                stateManager.setState(HealingState.SUCCESS);
            } else {
                stateManager.setState(HealingState.FAILED, 'No fix returned from backend.');
            }
        } catch (err: any) {
            console.error('Self-healing failed', err);
            stateManager.setState(HealingState.FAILED, err.message);
        } finally {
            this.isHealing = false;
        }
    }

    private async showDiffView(originalUri: vscode.Uri, originalText: string, fixedCode: string) {
        // Create an in-memory document for the fixed code
        // VS Code allows providing virtual documents via TextDocumentContentProvider,
        // but for a quick diff we can use an untitled URI with a query parameter or just a custom scheme.

        // Alternatively, we can use the original uri for left, and an untitled file for right,
        // or a custom virtual document provider.
        // For simplicity, we can create a temporary file or workspace edit, but let's use a custom scheme.

        // VS Code Diff command takes (left, right, title)
        // We will register a TextDocumentContentProvider for 'supremeai-fix' scheme if not already registered.

        const rightUri = vscode.Uri.parse(`supremeai-fix:${originalUri.path}?fixed=true`);

        // Registering a temporary provider (ideally this should be registered once in initialize)
        const provider = new class implements vscode.TextDocumentContentProvider {
            provideTextDocumentContent(uri: vscode.Uri): string {
                return fixedCode;
            }
        };

        // We register it and then unregister after diff is closed or just keep it.
        const registration = vscode.workspace.registerTextDocumentContentProvider('supremeai-fix', provider);

        await vscode.commands.executeCommand(
            'vscode.diff',
            originalUri,
            rightUri,
            `SupremeAI Fix: ${originalUri.path.split('/').pop()}`
        );

        // We'll leave registration active for simplicity, though normally we'd clean it up.
    }
}

/**
 * Extracts the innermost semantic block (function/class) surrounding an error,
 * appended with all file imports.
 */
export async function getSemanticContext(document: vscode.TextDocument, errorLine: number): Promise<string> {
    let symbols: vscode.DocumentSymbol[] | undefined;

    try {
        symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
            'vscode.executeDocumentSymbolProvider',
            document.uri
        );
    } catch (e) {
        console.warn('[SupremeAI] Symbol provider failed. Falling back to heuristic.', e);
    }

    const imports = extractImports(document);
    let contextBlock = '';

    if (symbols && symbols.length > 0) {
        const targetSymbol = findInnermostSymbol(symbols, errorLine);
        if (targetSymbol) {
            contextBlock = document.getText(targetSymbol.range);
        }
    }

    // Fallback: 10-line heuristic if AST parsing fails or file lacks symbols
    if (!contextBlock) {
        const start = Math.max(0, errorLine - 10);
        const end = Math.min(document.lineCount - 1, errorLine + 10);
        contextBlock = document.getText(new vscode.Range(start, 0, end, document.lineAt(end).text.length));
    }

    return `// --- FILE IMPORTS ---\n${imports}\n\n// --- ERROR CONTEXT ---\n${contextBlock}`;
}

/**
 * Recursively searches the AST to find the deepest node encompassing the error.
 */
function findInnermostSymbol(symbols: vscode.DocumentSymbol[], line: number): vscode.DocumentSymbol | undefined {
    let innermost: vscode.DocumentSymbol | undefined;

    for (const symbol of symbols) {
        if (symbol.range.start.line <= line && symbol.range.end.line >= line) {
            innermost = symbol;

            // Dive deeper into children (e.g., a method inside a class)
            if (symbol.children && symbol.children.length > 0) {
                const childMatch = findInnermostSymbol(symbol.children, line);
                if (childMatch) {
                    innermost = childMatch;
                }
            }
        }
    }
    return innermost;
}

/**
 * Grabs all import/export statements to provide dependency context to the LLM.
 */
function extractImports(document: vscode.TextDocument): string {
    const text = document.getText();
    // Matches standard ES6 imports, requires, and exports.
    const importRegex = /^(?:import|export|const .*? = require).*?;/gm;
    const matches = text.match(importRegex);
    return matches ? matches.join('\n') : '// No external imports found';
}
