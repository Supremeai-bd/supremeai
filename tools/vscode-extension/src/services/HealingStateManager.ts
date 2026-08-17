import * as vscode from 'vscode';
import { BaseDisposable } from '../utils/BaseDisposable';

export enum HealingState {
    IDLE = 'IDLE',
    ANALYZING_ERROR = 'ANALYZING_ERROR',
    GENERATING_PATCH = 'GENERATING_PATCH',
    APPLYING_DIFF = 'APPLYING_DIFF',
    SUCCESS = 'SUCCESS',
    FAILED = 'FAILED'
}

export interface HealingStateEvent {
    state: HealingState;
    message?: string; // Optional message for errors or specific updates
}

export class HealingStateManager extends BaseDisposable {
    private static instance: HealingStateManager;
    private currentState: HealingState = HealingState.IDLE;

    // 🔥 VS Code Native EventEmitter
    private readonly _onDidChangeState = new vscode.EventEmitter<HealingStateEvent>();
    public readonly onDidChangeState = this._onDidChangeState.event;

    private constructor() {
        super();
        this.register(this._onDidChangeState);
    }

    public static getInstance(): HealingStateManager {
        if (!HealingStateManager.instance) {
            HealingStateManager.instance = new HealingStateManager();
        }
        return HealingStateManager.instance;
    }

    public setState(state: HealingState, message?: string) {
        this.currentState = state;
        this._onDidChangeState.fire({ state, message });

        // Error হলে একটি গ্লোবাল VS Code Notification দেখাবো
        if (state === HealingState.FAILED && message) {
            vscode.window.showErrorMessage(`SupremeAI Healing Error: ${message}`);
        }
    }

    public getState(): HealingState {
        return this.currentState;
    }
}
