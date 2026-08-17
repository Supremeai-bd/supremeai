import { vi, describe, it, test, expect, beforeEach, afterEach } from 'vitest';
import * as vscode from 'vscode';
import { AuthService } from '../src/services/AuthService';

vi.mock('vscode', () => ({
  window: {
    showInputBox: vi.fn(),
    showInformationMessage: vi.fn(),
    showErrorMessage: vi.fn(),
    showWarningMessage: vi.fn(),
    createOutputChannel: vi.fn().mockReturnValue({ appendLine: vi.fn(), show: vi.fn() }),
  },
  commands: {
    executeCommand: vi.fn().mockResolvedValue(undefined),
    registerCommand: vi.fn().mockReturnValue({ dispose: vi.fn() }),
  },
  workspace: {
    isTrusted: true,
    getConfiguration: vi.fn().mockReturnValue({
      get: vi.fn(),
      update: vi.fn().mockResolvedValue(undefined),
    }),
    workspaceFolders: [],
    onDidSaveTextDocument: vi.fn().mockReturnValue({ dispose: vi.fn() }),
  },
  authentication: {
    getSession: vi.fn().mockResolvedValue(undefined),
  },
  EventEmitter: vi.fn().mockImplementation(() => ({
    event: vi.fn(),
    fire: vi.fn(),
    dispose: vi.fn(),
  })),
}));

describe('AuthService', () => {
  let authService: any;

  beforeEach(() => {
    AuthService.resetInstance();
    authService = AuthService.getInstance({
      backendUrl: 'http://127.0.0.1:8080',
      enableRealTimeLearning: true,
      autoReportErrors: true,
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    authService.logout();
  });

  describe('initialization', () => {
    test('initial state is unauthenticated', () => {
      expect(authService.isAuthenticated()).toBe(false);
      expect(authService.getToken()).toBeNull();
      expect(authService.getUser()).toBeNull();
    });
  });

  describe('login', () => {
    test('prompts for API key and returns false if cancelled', async () => {
      // Mock showInputBox to return undefined (user cancelled)
      const mockShowInputBox = vscode.window.showInputBox as unknown as ReturnType<typeof vi.fn>;
      mockShowInputBox.mockResolvedValueOnce(undefined);

      const result = await authService.login();
      expect(result).toBe(false);
      expect(vscode.window.showInputBox).toHaveBeenCalled();
    });
  });

  describe('completeLogin', () => {
    test('completes login, sets token/user and sets context to authenticated', async () => {
      const mockToken = 'mock-jwt-token';
      const mockUser = { username: 'dev-user' };
      await authService.completeLogin(mockToken, mockUser);

      expect(authService.isAuthenticated()).toBe(true);
      expect(authService.getToken()).toBe(mockToken);
      expect(authService.getUser()).toEqual(mockUser);
      expect(vscode.commands.executeCommand).toHaveBeenCalledWith(
        'setContext',
        'supremeai.authenticated',
        true
      );
    });
  });

  describe('logout', () => {
    test('clears token and user, resets VS Code context', async () => {
      authService.setToken('existing-token');
      authService.setUser({ username: 'dev' });

      await authService.logout();

      expect(authService.isAuthenticated()).toBe(false);
      expect(authService.getToken()).toBeNull();
      expect(authService.getUser()).toBeNull();
      expect(vscode.commands.executeCommand).toHaveBeenCalledWith(
        'setContext',
        'supremeai.authenticated',
        false
      );
      expect(vscode.window.showInformationMessage).toHaveBeenCalledWith(
        expect.stringContaining('Logged out')
      );
    });
  });
});
