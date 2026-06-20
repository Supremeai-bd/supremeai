import * as vscode from 'vscode';

import { SupremeAIConfig } from '../types';

export class AuthService {
  private static instance: AuthService;
  private config: SupremeAIConfig;
  private token: string | null = null;
  private user: any | null = null;

  private constructor(config: SupremeAIConfig) {
    this.config = config;
    this.token = null;
    this.user = null;
    vscode.commands.executeCommand('setContext', 'supremeai.authenticated', false);
  }

  public static getInstance(config?: SupremeAIConfig): AuthService {
    if (!AuthService.instance && config) {
      AuthService.instance = new AuthService(config);
    }
    return AuthService.instance;
  }

  public static resetInstance(): void {
    AuthService.instance = null as any;
  }

  private resolveBaseUrl(): string {
    let baseUrl = (this.config.backendUrl || '').trim().replace(/\/$/, '');
    if (!baseUrl.startsWith('http')) {
      baseUrl = `https://${baseUrl}`;
    }
    return baseUrl;
  }

  public async login(): Promise<boolean> {
    try {
      if (!this.config.backendUrl) {
        throw new Error('Backend URL is not configured in settings.');
      }

      const baseUrl = this.resolveBaseUrl();
      const loginUrl = `${baseUrl}/auth/login`;
      console.log('[SupremeAI] Opening browser for login:', loginUrl);
      await vscode.env.openExternal(vscode.Uri.parse(loginUrl));
      vscode.window.showInformationMessage('Login page opened in your browser. After signing in, the extension will detect the callback and complete authentication.');
      return false;
    } catch (error: any) {
      console.error('[SupremeAI] Login error:', error);
      vscode.window.showErrorMessage(`Login failed: ${error.message}`);
      return false;
    }
  }

  public async register(username: string, password: string): Promise<boolean> {
    try {
      const baseUrl = this.resolveBaseUrl();
      const response = await fetch(`${baseUrl}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      return true;
    } catch (error: any) {
      console.error('[SupremeAI] Register error:', error);
      vscode.window.showErrorMessage(`Registration failed: ${error.message}`);
      return false;
    }
  }

  public async completeLogin(token: string, user: Record<string, any>): Promise<void> {
    const secretStorage = vscode.extensions.getExtension('supremeai.supremeai-vscode')?.extensionKind
      ? undefined
      : undefined;
    const store = vscode.workspace.trustedState;
    await vscode.workspace.getConfiguration('supremeai').update('aiApiKey', token, true);
    this.token = token;
    this.user = user;
    await vscode.commands.executeCommand('setContext', 'supremeai.authenticated', true);
  }

  public async loginAsGuest(): Promise<boolean> {
    this.token = null;
    this.user = null;
    await vscode.commands.executeCommand('setContext', 'supremeai.authenticated', false);
    return false;
  }

  public async logout(): Promise<void> {
    this.token = null;
    this.user = null;
    await vscode.commands.executeCommand('setContext', 'supremeai.authenticated', false);
    vscode.window.showInformationMessage('Logged out successfully.');
  }

  public getToken(): string | null {
    return this.token;
  }

  public getUser(): any | null {
    return this.user;
  }

  public isAuthenticated(): boolean {
    return !!this.token;
  }

  public async rotateApiKey(): Promise<string | null> {
    try {
      const baseUrl = this.resolveBaseUrl();
      const response = await fetch(`${baseUrl}/admin/keys/rotate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.isAuthenticated() && this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as any;
      const newKey = data.api_key ?? data.access_token;
      if (typeof newKey === 'string') {
        this.token = newKey;
        await vscode.workspace.getConfiguration('supremeai').update('aiApiKey', newKey, true);
      }
      return this.token;
    } catch (error: any) {
      console.error('[SupremeAI] API key rotation failed:', error);
      vscode.window.showErrorMessage(`API key rotation failed: ${error.message}`);
      return null;
    }
  }

  public setToken(token: string): void {
    this.token = token;
    vscode.commands.executeCommand('setContext', 'supremeai.authenticated', true);
  }

  public setUser(user: any): void {
    this.user = user;
  }
}
