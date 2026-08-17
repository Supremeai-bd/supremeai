/**
 * CrossAiObserverService — কাছের AI agents (Copilot, Gemini, Kilo, Cline, aider, ইত্যাদি)
 * এর কার্যক্রম পর্যবেক্ষণ করে evolution/learn endpoint-এ পাঠায় (platform-agnostic)।
 */

/**
 * অন্যান্য AI এজেন্ট চালু আছে কিনা সনাক্ত করার হিউরিস্টিক।
 * Desktop Electron-এ আমরা system clipboard / active window টাইটেল এ area ব্যবহার করতে পারি;
 * VS Code-এ terminals অথবা settings স্ক্যান করা হয়।
 */
const AGENT_KEYWORDS = ['copilot', 'gemini', 'kilo', 'cline', 'aider', 'continue', 'cursor', 'windsurf'];

export class CrossAiObserverService {
  private static _backendUrl = 'https://supremeai-api-lhlwyikwlq-uc.a.run.app/api/evolution/learn';

  public static initialize(): void {
    // eslint-disable-next-line no-console
    console.log('📡 [Cross-AI Observer] Standby Mode.');
  }

  /** কিছু টেক্সটে agent-activity আভাস খোঁজে। */
  public static isAgenticActivity(text: string): boolean {
    const lower = text.toLowerCase();
    return AGENT_KEYWORDS.some((kw) => lower.includes(kw));
  }

  /** ডেটাবেজে লার্নিং রিপোর্ট পাঠায়। */
  public static async reportLearning(opts: {
    type: string;
    approach: string;
    result: string;
    token?: string | null;
    backendUrl?: string;
  }): Promise<void> {
    const { type, approach, result, token, backendUrl } = opts;
    try {
      const url = backendUrl || CrossAiObserverService._backendUrl;
      const payload = {
        task: `Observed local device activity of type: ${type}`,
        approach,
        result,
        timestamp: new Date().toISOString(),
      };
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      await (await fetch(url, { method: 'POST', headers, body: JSON.stringify(payload) })).json();
      // eslint-disable-next-line no-console
      console.log('💾 [Cross-AI Learned] Intercepted workflow synced to Supreme Database Pool.');
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('❌ Failed to stream cross-AI observed metrics to backend:', error);
    }
  }
}