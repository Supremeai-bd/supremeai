import * as vscode from 'vscode';
import { BaseDisposable } from '../utils/BaseDisposable';

/**
 * Thin Client নীতি: বাহ্যিক 'fast-levenshtein' ডিপেন্ডেন্সি বাদ দিয়ে ইনলাইন
 * Levenshtein দূরত্ব অ্যালগরিদম ব্যবহার করা হলো (কম ডিপেন্ডেন্সি, কম বান্ডল সাইজ)।
 */
function levenshteinDistance(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  if (m === 0) return n;
  if (n === 0) return m;

  let prev = new Array<number>(n + 1);
  let curr = new Array<number>(n + 1);
  for (let j = 0; j <= n; j++) prev[j] = j;

  for (let i = 1; i <= m; i++) {
    curr[0] = i;
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(
        prev[j] + 1, // deletion
        curr[j - 1] + 1, // insertion
        prev[j - 1] + cost // substitution
      );
    }
    [prev, curr] = [curr, prev];
  }
  return prev[n];
}

export class TelemetryTracker extends BaseDisposable {
    private activePatches: Map<string, { originalErrorId: string, proposedPatch: string }> = new Map();
    private static instance: TelemetryTracker;

    private constructor() {
        super();
    }

    public static initialize(context: vscode.ExtensionContext): TelemetryTracker {
        if (!this.instance) {
            this.instance = new TelemetryTracker();
            // Listen to document saves
            this.instance.register(vscode.workspace.onDidSaveTextDocument(this.instance.handleDocumentSave.bind(this.instance)));
            context.subscriptions.push(this.instance);
        }
        return this.instance;
    }

  public static trackProposedPatch(filePath: string, errorId: string, patchText: string) {
    // Instance না থাকলে এখনই initialize করা হচ্ছে (silent fail প্রতিরোধ)
    if (!this.instance) {
      const context = { subscriptions: [] as vscode.Disposable[] } as unknown as vscode.ExtensionContext;
      this.instance = TelemetryTracker.initialize(context);
    }
    this.instance.activePatches.set(filePath, { originalErrorId: errorId, proposedPatch: patchText });
  }

    private async handleDocumentSave(document: vscode.TextDocument) {
        const filePath = document.uri.fsPath;
        const patchData = this.activePatches.get(filePath);

        if (!patchData) return; // Not tracking a patch for this file

        const savedText = document.getText();
        const proposedText = patchData.proposedPatch;

        // Calculate Levenshtein distance (inline implementation)
        const distance = levenshteinDistance(savedText, proposedText);
        const maxLength = Math.max(savedText.length, proposedText.length);
        const similarityScore = maxLength === 0 ? 1.0 : 1.0 - (distance / maxLength);

        let status = 'MODIFIED';
        if (similarityScore >= 0.98) { // 98% or more is considered ACCEPTED
            status = 'ACCEPTED';
        } else if (similarityScore <= 0.50) { // Dropped below 50% means REJECTED
            status = 'REJECTED';
        }

        await TelemetryTracker.sendTelemetry(patchData.originalErrorId, filePath, status, similarityScore);

        // Remove from active tracking after evaluation
        this.activePatches.delete(filePath);
    }

    private static async sendTelemetry(errorId: string, filePath: string, status: string, score: number) {
        try {
            // Replace with your actual backend URL from config
            const backendUrl = vscode.workspace.getConfiguration('supremeai').get('backendUrl', 'https://supremeai-api-lhlwyikwlq-uc.a.run.app');

            await fetch(`${backendUrl}/api/v1/swarm/telemetry/patch-result`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    error_id: errorId,
                    patch_id: `patch-${Date.now()}`, // Or generate a real UUID
                    file_path: filePath,
                    status: status,
                    similarity_score: score
                })
            });
            console.log(`[SupremeAI Telemetry] Sent: ${status} (Score: ${score.toFixed(2)})`);
        } catch (error) {
            console.error('[SupremeAI Telemetry] Failed to send telemetry:', error);
        }
    }
}
