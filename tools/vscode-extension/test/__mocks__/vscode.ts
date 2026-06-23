// tools/vscode-extension/test/__mocks__/vscode.ts
// Type-safe VS Code Mock Engine to eliminate dead-code and false positives.

export class Position {
    constructor(public readonly line: number, public readonly character: number) {}

    isBefore(other: Position): boolean {
        if (this.line < other.line) return true;
        if (this.line > other.line) return false;
        return this.character < other.character;
    }

    isAfter(other: Position): boolean {
        if (this.line > other.line) return true;
        if (this.line < other.line) return false;
        return this.character > other.character;
    }

    isEqual(other: Position): boolean {
        return this.line === other.line && this.character === other.character;
    }
}

export class Range {
    public readonly start: Position;
    public readonly end: Position;

    constructor(start: Position, end: Position);
    constructor(startLine: number, startCharacter: number, endLine: number, endCharacter: number);
    constructor(startOrLine: Position | number, endOrChar: Position | number, endLine?: number, endCharacter?: number) {
        if (typeof startOrLine === "number" && typeof endOrChar === "number" && typeof endLine === "number" && typeof endCharacter === "number") {
            this.start = new Position(startOrLine, endOrChar);
            this.end = new Position(endLine, endCharacter);
        } else if (startOrLine instanceof Position && endOrChar instanceof Position) {
            this.start = startOrLine;
            this.end = endOrChar;
        } else {
            throw new Error("Invalid Range constructor parameters");
        }
    }

    get isEmpty(): boolean {
        return this.start.isEqual(this.end);
    }
}

export class Selection extends Range {
    public readonly anchor: Position;
    public readonly active: Position;

    constructor(anchor: Position, active: Position) {
        super(anchor, active);
        this.anchor = anchor;
        this.active = active;
    }

    get isReversed(): boolean {
        return this.active.isBefore(this.anchor);
    }
}

// ⚡ Active Functional Namespaces using Jest Spies with proper type structures
export const window = {
    showInformationMessage: jest.fn().mockResolvedValue(undefined),
    showErrorMessage: jest.fn().mockResolvedValue(undefined),
    showWarningMessage: jest.fn().mockResolvedValue(undefined),
    activeTextEditor: undefined,
    visibleTextEditors: [],
    createStatusBarItem: jest.fn().mockReturnValue({
        command: undefined,
        text: "",
        show: jest.fn(),
        hide: jest.fn(),
        dispose: jest.fn()
    })
};

export const workspace = {
    getConfiguration: jest.fn().mockReturnValue({
        get: jest.fn(),
        update: jest.fn(),
        has: jest.fn()
    }),
    textDocuments: [],
    onDidChangeTextDocument: jest.fn().mockReturnValue({ dispose: jest.fn() }),
    onDidSaveTextDocument: jest.fn().mockReturnValue({ dispose: jest.fn() })
};

export const commands = {
    registerCommand: jest.fn().mockReturnValue({ dispose: jest.fn() }),
    executeCommand: jest.fn().mockResolvedValue(undefined)
};

export enum StatusBarAlignment {
    Left = 1,
    Right = 2
}

export enum OverviewRulerLane {
    Left = 1,
    Center = 2,
    Right = 4,
    Full = 7
}

export const ExtensionContext = jest.fn().mockImplementation(() => ({
    subscriptions: [],
    workspaceState: { get: jest.fn(), update: jest.fn() },
    globalState: { get: jest.fn(), update: jest.fn(), setKeysForSync: jest.fn() },
    extensionPath: "/mock/extension/path",
    storagePath: "/mock/storage/path",
    globalStoragePath: "/mock/global/storage/path",
    logPath: "/mock/log/path"
}));
