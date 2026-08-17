import * as vscode from 'vscode';
import axios from 'axios';

export class CrossAiObserverService {
    private static _backendUrl = 'https://supremeai-api-lhlwyikwlq-uc.a.run.app/api/evolution/learn';

    public static initialize(context: vscode.ExtensionContext) {
        console.log('📡 [Cross-AI Observer] Standby Mode.');
        // Performance optimization: Disabled aggressive onSave file text parsing to preserve RAM/CPU.
    }

    private static _isAgenticActivity(command: string): boolean {
        const agentKeywords = ['interpreter', 'claude', 'gpt', 'copilot', 'aider', 'autogen', 'swarm'];
        return agentKeywords.some(keyword => command.toLowerCase().includes(keyword));
    }

    // 💾 ডাটাবেজে ডাটা পাঠানোর সিঙ্ক মেকানিজম (Evolution Engine Sync)
    private static async _reportLearning(type: string, approach: string, result: string) {
        try {
            const payload = {
                task: `Observed local device activity of type: ${type}`,
                approach: approach,
                result: result,
                timestamp: new Date().toISOString()
            };

            // AuthService থেকে বর্তমান টোকেন ব্যবহার করা হলো (হার্ডকোডেড টোকেন নয়)
            const { AuthService } = require('./AuthService');
            const authService = AuthService.getInstance();
            const token = authService?.getToken();
            const headers: Record<string, string> = { 'Content-Type': 'application/json' };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            await axios.post(this._backendUrl, payload, { headers });
            console.log('💾 [Cross-AI Learned] Intercepted workflow synced to Supreme Database Pool.');
        } catch (error) {
            console.error('❌ Failed to stream cross-AI observed metrics to backend:', error);
        }
    }
}
