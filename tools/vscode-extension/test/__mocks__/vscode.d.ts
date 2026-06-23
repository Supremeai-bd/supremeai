export declare const window: {
    showInformationMessage: jest.Mock<any, any, any>;
    showErrorMessage: jest.Mock<any, any, any>;
    showWarningMessage: jest.Mock<any, any, any>;
    createWebviewPanel: jest.Mock<any, any, any>;
    activeTextEditor: undefined;
    visibleTextEditors: never[];
};
export declare const workspace: {
    getConfiguration: jest.Mock<any, any, any>;
    onDidChangeTextDocument: jest.Mock<any, any, any>;
    onDidSaveTextDocument: jest.Mock<any, any, any>;
};
export declare const commands: {
    executeCommand: jest.Mock<any, any, any>;
    registerCommand: jest.Mock<any, any, any>;
};
export declare const authentication: {
    getSession: jest.Mock<any, any, any>;
};
export declare class Range {
    start: any;
    end: any;
    constructor(start: any, end: any);
}
export declare class Position {
    line: number;
    character: number;
    constructor(line: number, character: number);
}
export declare class Selection {
    anchor: any;
    active: any;
    constructor(anchor: any, active: any);
}
export declare const ExtensionContext: jest.Mock<any, any, any>;
