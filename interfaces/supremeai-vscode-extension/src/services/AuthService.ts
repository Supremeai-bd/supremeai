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

  public async login(): Promise<boolean> {
    try {
      if (!this.config.backendUrl) {
        throw new Error('Backend URL is not configured in settings.');
      }

      let baseUrl = this.config.backendUrl.trim().replace(/\/$/, '');
      if (!baseUrl.startsWith('http')) {
        baseUrl = `https://${baseUrl}`;
      }

      const loginUrl = `${baseUrl}/api/auth/firebase-login`;
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

  public setToken(token: string): void {
    this.token = token;
    vscode.commands.executeCommand('setContext', 'supremeai.authenticated', true);
  }

  public setUser(user: any): void {
    this.user = user;
  }
}
