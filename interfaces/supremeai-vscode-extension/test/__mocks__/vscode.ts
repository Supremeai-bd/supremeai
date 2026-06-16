export const window = {
  showInformationMessage: jest.fn(),
  showErrorMessage: jest.fn(),
  showWarningMessage: jest.fn(),
  createWebviewPanel: jest.fn(),
  activeTextEditor: undefined,
  visibleTextEditors: [],
};

export const workspace = {
  getConfiguration: jest.fn().mockReturnValue({
    get: jest.fn(),
    update: jest.fn(),
  }),
  onDidChangeTextDocument: jest.fn(),
  onDidSaveTextDocument: jest.fn(),
};

export const commands = {
  executeCommand: jest.fn(),
  registerCommand: jest.fn(),
};

export const authentication = {
  getSession: jest.fn(),
};

export class Range {
  constructor(public start: any, public end: any) {}
}

export class Position {
  constructor(public line: number, public character: number) {}
}

export class Selection {
  constructor(public anchor: any, public active: any) {}
}

export const ExtensionContext = jest.fn();
