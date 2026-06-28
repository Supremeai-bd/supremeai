/**
 * SupremeAI Service - Communication with Backend Learning Engine
 * Handles all real-time learning data transmission
 */

import * as vscode from 'vscode';
import axios, { AxiosInstance } from 'axios';
import { AuthService } from './AuthService';
import {
  LearningUpload,
  LearningResponse,
  SupremeAIConfig,
  CodeEdit,
  ErrorReport,
  SuggestionFeedback,
  ChatMessage,
  ChatRequest,
  ChatResponse,
  CodeAnalysis,
  CodeFlowAnalysis,
  CodeFlowAnalysisRequest,
  CodeFlowAnalysisResponse,
  ErrorResolutionRequest,
  ErrorResolutionResponse,
  SecurityIssue,
  HealthScore,
  DependencyGraph
} from '../types';

export class SupremeAIService {
  private client: AxiosInstance;
  private config: SupremeAIConfig;
  private sessionId: string;

  constructor(config: SupremeAIConfig) {
    this.config = config;
    this.sessionId = this.generateSessionId();

    // Configure Axios instance with defaults
    this.client = axios.create({
      baseURL: config.backendUrl,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for logging and auth
    this.client.interceptors.request.use((request) => {
      const authService = AuthService.getInstance();
      if (authService && authService.isAuthenticated()) {
        const token = authService.getToken();
        if (token) {
          request.headers['Authorization'] = `Bearer ${token}`;
        }
      }
      console.log(`[SupremeAI] Sending ${request.method?.toUpperCase()} to ${request.url}`);
      return request;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error(`[SupremeAI] API Error: ${error.message}`);
        return Promise.reject(error);
      }
    );
  }

  /**
   * Send code edit event for learning
   * POST /api/knowledge/learn
   */
  async sendCodeEdit(edit: CodeEdit): Promise<LearningResponse> {
    if (!this.config.enableRealTimeLearning) {
      return { success: false, message: 'Real-time learning disabled' };
    }

    try {
      const payload: LearningUpload = {
        type: 'CODE_EDIT',
        data: edit,
        sessionId: this.sessionId,
      };

      const response = await this.client.post<LearningResponse>('/api/knowledge/learn', payload);
      console.log(`[SupremeAI] Code edit learned: ${edit.taskId}`);
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to send code edit: ${error.message}`);
      return {
        success: false,
        message: error.message || 'Failed to send code edit',
      };
    }
  }

  /**
   * Report error for learning
   * POST /api/knowledge/failure
   */
  async reportError(error: ErrorReport): Promise<LearningResponse> {
    if (!this.config.autoReportErrors) {
      return { success: false, message: 'Auto-error reporting disabled' };
    }

    try {
      const payload: LearningUpload = {
        type: 'ERROR_REPORT',
        data: error,
        sessionId: this.sessionId,
      };

      const response = await this.client.post<LearningResponse>('/api/knowledge/failure', payload);
      console.log(`[SupremeAI] Error reported: ${error.errorType} at ${error.filePath}:${error.lineNumber}`);
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to report error: ${error.message}`);
      return {
        success: false,
        message: error.message || 'Failed to report error',
      };
    }
  }

  /**
   * Send suggestion feedback (accept/reject)
   * POST /api/knowledge/feedback
   */
  async sendFeedback(feedback: SuggestionFeedback): Promise<LearningResponse> {
    try {
      const payload: LearningUpload = {
        type: 'SUGGESTION_FEEDBACK',
        data: feedback,
        sessionId: this.sessionId,
      };

      const response = await this.client.post<LearningResponse>('/api/knowledge/feedback', payload);
      console.log(`[SupremeAI] Feedback sent: ${feedback.accepted ? 'accepted' : 'rejected'}`);
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to send feedback: ${error.message}`);
      return {
        success: false,
        message: error.message || 'Failed to send feedback',
      };
    }
  }

  /**
   * Send code analysis snapshot
   * POST /api/knowledge/analysis
   */
  async sendCodeAnalysis(filePath: string, code: string, language: string): Promise<LearningResponse> {
    if (!this.config.enableRealTimeLearning) {
      return { success: false, message: 'Real-time learning disabled' };
    }

    try {
      const analysis = {
        filePath,
        code,
        language,
        timestamp: new Date().toISOString(),
        metrics: this.analyzeCodeMetrics(code, language),
      };

      const response = await this.client.post<LearningResponse>('/api/knowledge/analysis', {
        ...analysis,
        sessionId: this.sessionId,
      });

      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to send analysis: ${error.message}`);
      return { success: false, message: error.message };
    }
  }

  /**
   * ভেক্টর মেমোরিতে ফাইল সিঙ্ক করার ফাংশন
   * POST /api/memory/ingest
   */
  async syncFileToMemory(filePath: string, content: string, language: string): Promise<any> {
    try {
      const response = await this.client.post('/api/memory/ingest', {
        filePath,
        content,
        language,
        sessionId: this.sessionId,
        timestamp: new Date().toISOString()
      });
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] ভেক্টর মেমোরি সিঙ্ক ব্যর্থ হয়েছে: ${error.message}`);
      return { success: false, message: error.message };
    }
  }

  async getInlineCompletions(prefix: string, suffix: string, filePath: string, language: string): Promise<{ success: boolean; suggestions: string[] }> {
    try {
      const response = await this.client.post<{ success: boolean; suggestions: string[] }>('/api/chat/completion', {
        prefix,
        suffix,
        filePath,
        language,
        sessionId: this.sessionId,
      });
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Inline completion request failed: ${error.message}`);
      return { success: false, suggestions: [] };
    }
  }

  /**
   * Send chat message
   * POST /api/chat/message
   */
  async sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    try {
      const response = await this.client.post<ChatResponse>('/api/chat/message', {
        ...request,
        sessionId: this.sessionId,
      });
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Chat error: ${error.message}`);
      try {
        const fallbackReply = await this.tryFreeModelFallback(this.buildContextAwareMessage(request));
        return {
          success: true,
          message: 'Success (Fallback)',
          response: fallbackReply,
          sessionId: this.sessionId,
          timestamp: new Date().toISOString()
        };
      } catch (fallbackError: any) {
        throw new Error(`Backend error: ${error.message}. Fallback failed: ${fallbackError.message}`);
      }
    }
  }

  private buildContextAwareMessage(request: ChatRequest): string {
    let fullMessage = request.message || '';
    const contextParts: string[] = [];
    if (request.filePath) contextParts.push(`File: ${request.filePath}`);
    if (request.language) contextParts.push(`Language: ${request.language}`);
    const code = (request as any).codeContext || (request as any).code;
    if (code) {
      contextParts.push(`Code:\n\`\`\`\n${code}\n\`\`\``);
    }
    if (contextParts.length > 0) {
      fullMessage += '\n\n--- Context ---\n' + contextParts.join('\n');
    }
    return fullMessage;
  }

  private async tryFreeModelFallback(message: string, onToken?: (token: string) => void): Promise<string> {
    const config = vscode.workspace.getConfiguration('supremeai');
    const provider = config.get<string>('apiProvider') || 'openrouter';
    const apiKey = config.get<string>('aiApiKey') || '';
    const model = config.get<string>('aiModel') || 'openrouter/anthropic/claude-3.5-sonnet';

    if (provider === 'ollama') {
      try {
        console.log('[SupremeAI] Fallback to Ollama local...');
        const response = await fetch('http://localhost:11434/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: model || 'codellama',
            messages: [{ role: 'user', content: message }],
            stream: !!onToken
          })
        });
        if (!response.ok) throw new Error(`Ollama returned status ${response.status}`);
        if (onToken && response.body) {
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let fullText = '';
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            const parts = chunk.split('\n');
            for (const part of parts) {
              if (!part.trim()) continue;
              try {
                const parsed = JSON.parse(part);
                const token = parsed.message?.content || '';
                fullText += token;
                onToken(token);
              } catch {}
            }
          }
          return fullText;
        } else {
          const data = await response.json() as any;
          return data.message?.content || '';
        }
      } catch (err: any) {
        console.error('[SupremeAI] Ollama fallback failed:', err.message);
        throw err;
      }
    } else {
      try {
        console.log('[SupremeAI] Fallback to OpenRouter/External API...');
        const actualApiKey = apiKey || '';
        const actualModel = model || 'openrouter/anthropic/claude-3.5-sonnet';
        const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${actualApiKey}`,
            'HTTP-Referer': 'https://github.com/paykaribazaronline/supremeai',
            'X-Title': 'SupremeAI VS Code Extension'
          },
          body: JSON.stringify({
            model: actualModel,
            messages: [{ role: 'user', content: message }],
            stream: !!onToken
          })
        });
        if (!response.ok) {
          const errText = await response.text();
          throw new Error(`OpenRouter returned status ${response.status}: ${errText}`);
        }
        if (onToken && response.body) {
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let fullText = '';
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            const parts = chunk.split('\n');
            for (const part of parts) {
              const trimmed = part.trim();
              if (!trimmed.startsWith('data:')) continue;
              const payload = trimmed.slice(5).trim();
              if (payload === '[DONE]') break;
              try {
                const parsed = JSON.parse(payload);
                const token = parsed.choices?.[0]?.delta?.content || '';
                fullText += token;
                onToken(token);
              } catch {}
            }
          }
          return fullText;
        } else {
          const data = await response.json() as any;
          return data.choices?.[0]?.message?.content || '';
        }
      } catch (err: any) {
        console.error('[SupremeAI] OpenRouter fallback failed:', err.message);
        throw err;
      }
    }
  }

  /**
   * Stream chat response
   * POST /api/chat/stream
   */
  async streamChatResponse(request: ChatRequest, onToken?: (token: string) => void): Promise<string> {
    return this.streamChatCompletion(request, onToken);
  }

  async streamChatCompletion(request: ChatRequest, onToken?: (token: string) => void): Promise<string> {
    try {
      const base = this.config.backendUrl.replace(/\/$/, '');
      const url = `${base}/api/chat/stream`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(AuthService.getInstance()?.getToken() ? { Authorization: `Bearer ${AuthService.getInstance()!.getToken()!}` } : {})
        },
        body: JSON.stringify({ ...request, stream: true }),
      });

      if (!response.ok) {
        throw new Error(`Stream failed with status ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No readable stream in response');
      }

      const decoder = new TextDecoder();
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const parts = chunk.split('\n');
        for (const part of parts) {
          const trimmed = part.trim();
          if (!trimmed.startsWith('data:')) continue;
          const payload = trimmed.slice(5).trim();
          if (payload === '[DONE]') break;
          try {
            const parsed = JSON.parse(payload);
            const token = parsed.token ?? parsed.content ?? parsed.text ?? '';
            if (typeof token === 'string' && token) {
              fullText += token;
              onToken?.(token);
            }
          } catch {
            if (payload) {
              fullText += payload;
              onToken?.(payload);
            }
          }
        }
      }

      return fullText;
    } catch (error: any) {
      console.error(`[SupremeAI] Completion stream error: ${error.message}`);
      try {
        return await this.tryFreeModelFallback(this.buildContextAwareMessage(request), onToken);
      } catch (fallbackError: any) {
        throw new Error(`Backend stream error: ${error.message}. Fallback failed: ${fallbackError.message}`);
      }
    }
  }

  /**
   * Get chat history
   * GET /api/chat/history
   */
  async getChatHistory(sessionId?: string): Promise<ChatMessage[]> {
    try {
      const response = await this.client.get('/api/chat/history', {
        params: { sessionId: sessionId || this.sessionId }
      });
      return response.data.messages || [];
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to get chat history: ${error.message}`);
      return [];
    }
  }

  async saveCheckpoint(taskId: string, stepIndex: number, state: Record<string, any>): Promise<boolean> {
    try {
      const response = await this.client.post('/api/memory/checkpoint', {
        task_id: taskId,
        step_index: stepIndex,
        state,
        sessionId: this.sessionId,
      });
      return response.data?.task_id === taskId;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to save checkpoint: ${error.message}`);
      return false;
    }
  }

  async loadCheckpoint(taskId: string): Promise<any | null> {
    try {
      const response = await this.client.get(`/api/memory/checkpoint/${taskId}`);
      return response.data ?? null;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to load checkpoint: ${error.message}`);
      return null;
    }
  }

  async buildMemoryContext(documents: string[], query: string, sessionId: string, budget = 4000): Promise<string> {
    try {
      const response = await this.client.post('/api/memory/context', {
        documents,
        query,
        session_id: sessionId,
        budget,
      });
      return response.data?.context || '';
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to build memory context: ${error.message}`);
      return '';
    }
  }

  /**
   * Clear chat history
   * DELETE /api/chat/history
   */
  async clearChatHistory(sessionId?: string): Promise<boolean> {
    try {
      await this.client.delete('/api/chat/history', {
        data: { sessionId: sessionId || this.sessionId }
      });
      return true;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to clear chat history: ${error.message}`);
      return false;
    }
  }

  /**
   * Generate fallback response when backend is unavailable
   */
  private generateFallbackResponse(message: string): string {
    const lowerMsg = message.toLowerCase();

    if (lowerMsg.includes('bangla') || lowerMsg.includes('বাংলা')) {
      return 'হ্যাঁ, আমি বাংলায় কথা বলতে পারি! আমি আপনার সুপ্রিমএআই (SupremeAI) অ্যাসিস্ট্যান্ট। আমি আপনাকে কোডিং, বাগ ফিক্সিং এবং কোড রিফ্যাক্টরিংয়ে সাহায্য করতে পারি। আপনার প্রশ্নটি বাংলায় করতে পারেন।';
    }

    if (lowerMsg.includes('hello') || lowerMsg.includes('hi') || lowerMsg.includes('hey')) {
      return 'Hello! I\'m your SupremeAI assistant. How can I help you with your code today?';
    }

    if (lowerMsg.includes('bug') || lowerMsg.includes('error') || lowerMsg.includes('fix')) {
      return 'I can help you debug! Please share the error message or the problematic code, and I\'ll analyze it for you.';
    }

    if (lowerMsg.includes('refactor') || lowerMsg.includes('improve') || lowerMsg.includes('optimize')) {
      return 'I can help refactor your code! Please share the code you\'d like to improve, and I\'ll suggest optimizations.';
    }

    if (lowerMsg.includes('explain') || lowerMsg.includes('understand')) {
      return 'I can explain code concepts! Please share the code or concept you\'d like me to explain.';
    }

    return 'I\'m here to help with your coding needs! You can ask me to:\n' +
      '• Explain code\n' +
      '• Fix bugs\n' +
      '• Refactor code\n' +
      '• Review code\n' +
      '• Answer programming questions\n\n' +
      'Please share your code or question, and I\'ll do my best to help!';
  }

  /**
   * Get learning statistics
   * GET /api/knowledge/stats
   */
  async getLearningStats(): Promise<any> {
    try {
      const response = await this.client.get('/api/knowledge/stats');
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to get stats: ${error.message}`);
      return null;
    }
  }

  /**
   * Generate unique session ID for this VS Code session
   */
  private generateSessionId(): string {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(7);
    return `vscode-${timestamp}-${random}`;
  }

  /**
   * Run CodeFlow analysis on repository
   * POST /api/codeflow/analyze
   */
  async analyzeRepository(request: CodeFlowAnalysisRequest): Promise<CodeFlowAnalysisResponse> {
    try {
      const response = await this.client.post<CodeFlowAnalysisResponse>('/api/codeflow/analyze', {
        ...request,
        sessionId: this.sessionId,
      });
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] CodeFlow analysis failed: ${error.message}`);
      return {
        success: false,
        analysisId: '',
        data: {
          repositoryId: '',
          files: [],
          dependencies: { nodes: [], edges: [] },
          patterns: [],
          securityIssues: [],
          healthScore: { score: 0, grade: 'F', breakdown: { security: 0, maintainability: 0, complexity: 0, documentation: 0, testing: 0 }, details: [] },
          analysisTimestamp: new Date().toISOString(),
          status: 'failed',
        },
        message: error.message,
      };
    }
  }

  /**
   * Get CodeFlow analysis results
   * GET /api/codeflow/analysis/:id
   */
  async getAnalysisResults(analysisId: string): Promise<CodeFlowAnalysis | null> {
    try {
      const response = await this.client.get<CodeFlowAnalysis>(`/api/codeflow/analysis/${analysisId}`);
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to get analysis results: ${error.message}`);
      return null;
    }
  }

  /**
   * Get cached analysis for repository
   * GET /api/codeflow/repository/:id/analysis
   */
  async getRepositoryAnalysis(repositoryId: string): Promise<CodeFlowAnalysis | null> {
    try {
      const response = await this.client.get<CodeFlowAnalysis>(`/api/codeflow/repository/${repositoryId}/analysis`);
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to get repository analysis: ${error.message}`);
      return null;
    }
  }

  /**
   * Resolve error with AI-powered suggestions
   * POST /api/codeflow/error/resolve
   */
  async resolveError(request: ErrorResolutionRequest): Promise<ErrorResolutionResponse> {
    try {
      const response = await this.client.post<ErrorResolutionResponse>('/api/codeflow/error/resolve', {
        ...request,
        sessionId: this.sessionId,
      });
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Error resolution failed: ${error.message}`);
      return {
        success: false,
        rootCause: 'Unable to determine root cause',
        affectedFiles: [],
        blastRadius: [],
        suggestedFixes: [],
        confidence: 0,
      };
    }
  }

  /**
   * Get security issues for repository
   * GET /api/codeflow/repository/:id/security
   */
  async getSecurityIssues(repositoryId: string, severity?: string): Promise<SecurityIssue[]> {
    try {
      const response = await this.client.get<SecurityIssue[]>(`/api/codeflow/repository/${repositoryId}/security`, {
        params: { severity },
      });
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to get security issues: ${error.message}`);
      return [];
    }
  }

  /**
   * Get dependency graph for repository
   * GET /api/codeflow/repository/:id/dependencies
   */
  async getDependencyGraph(repositoryId: string): Promise<DependencyGraph | null> {
    try {
      const response = await this.client.get<DependencyGraph>(`/api/codeflow/repository/${repositoryId}/dependencies`);
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to get dependency graph: ${error.message}`);
      return null;
    }
  }

  /**
   * Get health score for repository
   * GET /api/codeflow/repository/:id/health
   */
  async getHealthScore(repositoryId: string): Promise<HealthScore | null> {
    try {
      const response = await this.client.get<HealthScore>(`/api/codeflow/repository/${repositoryId}/health`);
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to get health score: ${error.message}`);
      return null;
    }
  }

  /**
   * Quick metrics analysis for code
    */
  private analyzeCodeMetrics(code: string, language: string): Record<string, number> {
    const lines = code.split('\n');
    return {
      linesOfCode: lines.length,
      nonEmptyLines: lines.filter(l => l.trim().length > 0).length,
      commentLines: language === 'typescript' || language === 'javascript'
        ? lines.filter(l => l.trim().startsWith('//') || l.trim().startsWith('/*')).length
        : 0,
      complexityEstimate: this.estimateComplexity(code),
    };
  }

  private estimateComplexity(code: string): number {
    // Simple cyclomatic complexity approximation
    const decisionPoints = (code.match(/\b(if|else|for|while|switch|case|catch)\b/g) || []).length;
    return decisionPoints + 1;
  }

  /**
   * Update configuration at runtime
   */
  updateConfig(newConfig: Partial<SupremeAIConfig>): void {
    this.config = { ...this.config, ...newConfig };
  }

  /**
   * Register a proposed feature detected in environment
   */
  async registerProposedFeature(feature: any): Promise<any> {
    try {
      const response = await this.client.post('/api/features/propose', feature);
      return response.data;
    } catch (error: any) {
      console.error(`[SupremeAI] Failed to register proposed feature: ${error.message}`);
      return { success: false, message: error.message };
    }
  }

  /**
   * Get current session ID
   */
  getSessionId(): string {
    return this.sessionId;
  }
}

/**
 * Singleton instance
 */
let supremeAIService: SupremeAIService | null = null;

export function getSupremeAIService(config?: SupremeAIConfig): SupremeAIService {
  if (!supremeAIService && config) {
    supremeAIService = new SupremeAIService(config);
  }
  if (!supremeAIService) {
    throw new Error('SupremeAIService not initialized. Call getSupremeAIService(config) first.');
  }
  return supremeAIService;
}

export function setSupremeAIService(service: SupremeAIService): void {
  supremeAIService = service;
}
