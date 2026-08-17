/**
 * ScopeGuardService - Dynamic permission scope for target repositories
 * Protected main repos default to READ_ONLY; explicit JIT OTP binding enables write.
 */

import { BaseDisposable } from '../utils/BaseDisposable';

export enum PermissionScope {
  READ_ONLY = 'READ_ONLY',
  READ_WRITE = 'READ_WRITE',
  ADMIN = 'ADMIN',
}

export class ScopeGuardService extends BaseDisposable {
  private static instance: ScopeGuardService;
  private currentScope: PermissionScope = PermissionScope.READ_ONLY;

  private constructor() {
    super();
  }

  public static getInstance(): ScopeGuardService {
    if (!ScopeGuardService.instance) {
      ScopeGuardService.instance = new ScopeGuardService();
    }
    return ScopeGuardService.instance;
  }

  public async detectCurrentScope(): Promise<PermissionScope> {
    // Protected main repos default to READ_ONLY
    // In future: check against backend admin-api for JIT OTP status
    return this.currentScope;
  }

  public isReadOnly(): boolean {
    return this.currentScope === PermissionScope.READ_ONLY;
  }

  public canWrite(): boolean {
    return this.currentScope === PermissionScope.READ_WRITE;
  }

  public async elevateScope(newScope: PermissionScope): Promise<boolean> {
    // Future: verify JIT OTP before elevating scope
    this.currentScope = newScope;
    return true;
  }
}