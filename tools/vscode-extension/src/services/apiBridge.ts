/**
 * SupremeExtensionBridge - Resilient, type-safe bridge between the VS Code
 * extension and the SupremeAI backend.
 *
 * এই ক্লাসটি এক্সটেনশন থেকে ব্যাকএন্ডে রিকোয়েস্ট পাঠানোর জন্য একটি কেন্দ্রীয় (centralized)
 * আর্কিটেকচার সরবরাহ করে। সরাসরি `fetch` কল বা ম্যানুয়াল মক-এর বদলে একটি axios
 * ইনস্ট্যান্স ব্যবহার করে যা:
 *   - `X-Correlation-ID` হেডার ইনজেক্ট করে (ডিবাগিং ও ট্রেসিংয়ের জন্য)
 *   - `AuthService` থেকে টোকেন নেয় (প্রজেক্টের এস্টাব্লিশড প্যাটার্ন)
 *   - 401 এ নিজে থেকেই `supremeai.login` ট্রিগার করে
 *   - সব এরর VS Code Output Channel-এ লগ করে (silent failure নেই)
 */

import * as vscode from 'vscode';
import axios, { AxiosInstance, AxiosError } from 'axios';

import { AuthService } from './AuthService';
import { SupremeAIConfig } from '../types';

// ব্যাকএন্ডের প্রোডাকশন এন্ডপয়েন্ট (package.json এর ডিফল্ট ভ্যালুর সাথে মিল রাখা হয়েছে)
const DEFAULT_BACKEND_URL = 'https://supremeai-api-lhlwyikwlq-uc.a.run.app';

// টাইপ-সেফ রেস্পন্স কন্ট্রাক্ট
export interface EvolveCodeResult {
  evolvedCode: string;
  model?: string;
  tokensUsed?: number;
}

export interface BridgeRequestOptions {
  timeoutMs?: number;
  correlationId?: string;
}

export class SupremeExtensionBridge {
  private client: AxiosInstance;
  private readonly baseUrl: string;
  private readonly extSessionId: string;

  constructor(config?: SupremeAIConfig) {
    // `supremeai.backendUrl` কনফিগ থেকে URL নেওয়া হচ্ছে (SupremeAIService-এর সাথে কনসিসটেন্ট)
    const configured =
      config?.backendUrl ||
      vscode.workspace.getConfiguration('supremeai').get<string>('backendUrl');

    this.baseUrl = (configured || DEFAULT_BACKEND_URL).replace(/\/$/, '');
    this.extSessionId = vscode.env.sessionId || `vscode-${Date.now()}`;

    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 10000,
      headers: { 'Content-Type': 'application/json' },
    });

    this.initializeInterceptors();
  }

  private initializeInterceptors(): void {
    // বাংলা মন্তব্য: প্রতিটি রিকোয়েস্টে অথোরাইজেশন + করিলেশন আইডি ইনজেক্ট করা হচ্ছে
    this.client.interceptors.request.use(async (config) => {
      const token = await this.resolveToken();
      if (token) {
        config.headers.set('Authorization', `Bearer ${token}`);
      }

      const traceId = `vscode-${this.extSessionId}-${Date.now()}`;
      config.headers.set('X-Correlation-ID', traceId);
      return config;
    });

    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (error.response?.status === 401) {
          vscode.window.showErrorMessage(
            'SupremeAI: Auth Token Expired. Please login again.'
          );
          await vscode.commands.executeCommand('supremeai.login');
        }
        this.logError(error);
        return Promise.reject(error);
      }
    );
  }

  /**
   * টোকেন রেজলভ করে — আগে AuthService (এস্টাব্লিশড প্যাটার্ন), ব্যর্থ হলে
   * VS Code এর নেটিভ authentication API থেকে ফলব্যাক করে।
   */
  private async resolveToken(): Promise<string | undefined> {
    const fromService = AuthService.getInstance()?.getToken();
    if (fromService) {
      return fromService;
    }
    try {
      const session = await vscode.authentication.getSession('supremeai', [
        'read',
        'write',
      ]);
      return session?.accessToken;
    } catch {
      return undefined;
    }
  }

  private logError(error: unknown): void {
    const channel = vscode.window.createOutputChannel('SupremeAI Errors');
    const timestamp = new Date().toISOString();
    if (axios.isAxiosError(error)) {
      channel.appendLine(`[${timestamp}] API AxiosError: ${error.message}`);
      if (error.response) {
        const detail = JSON.stringify(error.response.data);
        channel.appendLine(`Status: ${error.response.status} | Details: ${detail}`);
      }
    } else if (error instanceof Error) {
      channel.appendLine(`[${timestamp}] Non-Axios Error: ${error.message}`);
    } else {
      channel.appendLine(`[${timestamp}] Unknown Error: ${String(error)}`);
    }
  }

  /**
   * Autonomous Action: ব্যাকএন্ডের `/agents/evolve-code` এন্ডপয়েন্টে কোড পাঠিয়ে
   * ইভলভ করে। রিটার্ন টাইপ স্পষ্টভাবে টাইপ করা হয়েছে।
   */
  public async triggerCodeEvolution(
    codeSnippet: string,
    options?: BridgeRequestOptions
  ): Promise<string> {
    try {
      const response = await this.client.post<EvolveCodeResult>(
        '/agents/evolve-code',
        { code: codeSnippet },
        { timeout: options?.timeoutMs }
      );
      return response.data.evolvedCode;
    } catch (error) {
      vscode.window.showErrorMessage(
        'SupremeAI: Failed to evolve code. Check output channel.'
      );
      throw error;
    }
  }

  /**
   * জেনেরিক POST হেল্পার — ভবিষ্যতের কমান্ডগুলো এই ব্রিজের মাধ্যমেই যাতে
   * রিকোয়েস্ট করতে পারে (Brittle architecture এড়ানোর জন্য)।
   */
  public async post<T = unknown>(
    path: string,
    payload: unknown,
    options?: BridgeRequestOptions
  ): Promise<T> {
    const response = await this.client.post<T>(path, payload, {
      timeout: options?.timeoutMs,
    });
    return response.data;
  }

  /**
   * 100+ রেজিস্টার্ড টার্গেট রেপো ও প্ল্যাটফর্মের লাইভ পারমিশন স্কোপ ফ্রেচ করে।
   * ব্যাকএন্ড অফলাইন থাকলে নিরাপদ খালি অ্যারে রিটার্ন করে যাতে UI সঠিক Offline স্টেট দেখাতে পারে।
   */
  public async fetchTargetRepositories(): Promise<any[]> {
    try {
      const response = await this.client.get<any[]>('/admin-api/workspaces/targets');
      return response.data || [];
    } catch {
      return [];
    }
  }


  /**
   * নতুন টার্গেট রেপো বা প্ল্যাটফর্ম ডাইনামিক্যালি বাইন্ড করে (JIT OTP protected)।
   */
  public async bindTargetRepository(payload: any, otpCode?: string): Promise<any> {
    const headers: Record<string, string> = {};
    if (otpCode) {
      headers['X-JIT-OTP'] = otpCode;
    }
    const response = await this.client.post<any>('/admin-api/workspaces/bind-target', payload, { headers });
    return response.data;
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }
}

let _apiBridgeSingleton: SupremeExtensionBridge | null = null;

export function getApiBridge(config?: SupremeAIConfig): SupremeExtensionBridge {
  if (!_apiBridgeSingleton) {
    _apiBridgeSingleton = new SupremeExtensionBridge(config);
  }
  return _apiBridgeSingleton;
}

// মডিউল লোডের সময় ইন্সট্যান্স তৈরি করা হয় না — getApiBridge() কল করলেই তৈরি হবে (লেজি ইনিশিয়ালাইজেশন)
// export const apiBridge = getApiBridge();
// export const apiBridgeInstance = apiBridge;


