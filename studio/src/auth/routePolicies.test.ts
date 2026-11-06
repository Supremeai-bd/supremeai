import { describe, expect, it } from 'vitest';
import { canAccessRoute, getRoutePolicy } from './routePolicies';

describe('canonical route policies', () => {
  it('uses longest-prefix matching for admin routes', () => {
    expect(getRoutePolicy('/admin/security')?.requiredRole).toBe('admin');
    expect(getRoutePolicy('/workspace/agent')?.requiredRole).toBe('user');
  });

  it('keeps admin routes unavailable to regular users', () => {
    expect(canAccessRoute('/admin', 'user')).toBe(false);
    expect(canAccessRoute('/admin/security', 'admin')).toBe(true);
  });

  it('keeps internal telemetry routes inside the admin boundary', () => {
    expect(getRoutePolicy('/cockpit')?.requiredRole).toBe('admin');
    expect(getRoutePolicy('/telemetry')?.requiredRole).toBe('admin');
    expect(canAccessRoute('/cockpit', 'user')).toBe(false);
    expect(canAccessRoute('/telemetry', 'admin')).toBe(true);
  });

  it('defers unknown permission data to the backend', () => {
    expect(canAccessRoute('/billing', 'user', [])).toBe(true);
    expect(canAccessRoute('/billing', 'user', ['profile.read'])).toBe(false);
    expect(canAccessRoute('/billing', 'user', ['billing.read'])).toBe(true);
  });
});
