import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ScopeGuardService, PermissionScope } from '../src/services/ScopeGuardService';

describe('ScopeGuardService', () => {
  let service: ScopeGuardService;

  beforeEach(() => {
    service = ScopeGuardService.getInstance();
  });

  it('should default to READ_ONLY for protected main repositories', async () => {
    const scope = await service.detectCurrentScope();
    expect(scope).toBe(PermissionScope.READ_ONLY);
    expect(service.isReadOnly()).toBe(true);
    expect(service.canWrite()).toBe(false);
  });
});
