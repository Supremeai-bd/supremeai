// ============================================================================
// file >> auth-service.test.ts
// project >> SupremeAI 2.0
// purpose >> User authentication
// module >> tools
// ============================================================================
const vscode = require('vscode');

const { AuthService } = require('../src/services/AuthService');

beforeAll(() => {
  vscode.window = {
    showInformationMessage: jest.fn(),
    showErrorMessage: jest.fn(),
    showWarningMessage: jest.fn(),
  };
  vscode.commands = {
    executeCommand: jest.fn().mockResolvedValue(undefined),
  };
  vscode.authentication = {
    getSession: jest.fn(),
  };
  vscode.env = {
    openExternal: jest.fn().mockResolvedValue(true),
  };
  vscode.Uri = {
    parse: jest.fn().mockImplementation((val) => ({ toString: () => val })),
  };
  vscode.workspace = {
    getConfiguration: jest.fn().mockReturnValue({
      update: jest.fn().mockResolvedValue(undefined),
      get: jest.fn().mockReturnValue(''),
    }),
    isTrusted: true,
  };
  vscode.extensions = {
    getExtension: jest.fn().mockReturnValue({
      extensionKind: 1,
    }),
  };
});

describe('AuthService', () => {
  let authService: any;

  beforeEach(() => {
    AuthService.resetInstance();
    authService = AuthService.getInstance({
      backendUrl: 'http://127.0.0.1:8080',
      enableRealTimeLearning: true,
      autoReportErrors: true,
    });
    jest.clearAllMocks();
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
    test('opens browser URL and returns false', async () => {
      const result = await authService.login();
      expect(result).toBe(false);
      expect(vscode.env.openExternal).toHaveBeenCalled();
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
