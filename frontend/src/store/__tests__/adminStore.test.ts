/**
 * #3269: adminStore — Vitest coverage (state contract + login flows).
 *
 * বাংলা: useAdminStore-এর আসল চুক্তি — initial state, setters, trusted-browser
 * login, otp_required transition, TOTP setup, logout।
 * Mock-strategy বিদ্যমান src/store/adminStore.test.ts-এর pattern অনুসরণ করে
 * (vi.hoisted + vi.mock — ESM-safe; require() নয়)।
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

const { fakeAuth, firebaseLogin, firebaseTotpSetup, setAdminToken, getAdminToken, clearAdminToken, updateTokenCache } =
  vi.hoisted(() => ({
    fakeAuth: {
      currentUser: {
        getIdToken: vi.fn().mockResolvedValue('id-token-abc'),
        email: 'admin@example.com',
      },
    },
    firebaseLogin: vi.fn(),
    firebaseTotpSetup: vi.fn(),
    setAdminToken: vi.fn(),
    getAdminToken: vi.fn().mockReturnValue(null), // default: no stored token
    clearAdminToken: vi.fn(),
    updateTokenCache: vi.fn(),
  }));

vi.mock('../../firebase', () => ({
  getFirebaseAuth: vi.fn().mockResolvedValue(fakeAuth),
}));

vi.mock('firebase/auth', () => ({
  signInWithEmailAndPassword: vi.fn(),
  signOut: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('../../services/authService', () => ({
  authService: {
    firebaseLogin,
    firebaseTotpSetup,
    firebaseTotpVerify: vi.fn(),
    firebaseTotpRecover: vi.fn(),
  },
}));

vi.mock('../../services/apiClient', () => ({
  updateTokenCache,
}));

vi.mock('../../services/tokenStorage', () => ({
  setAdminToken,
  getAdminToken,
  clearAdminToken,
}));

import { useAdminStore } from '../adminStore';

// বাংলা: ছোট helper — JWT payload → base64 (store-এর decodeJwt-এর সাথে সামঞ্জস্যপূর্ণ)
function makeJwt(payload: Record<string, unknown>): string {
  const b64 = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `header.${b64(payload)}.signature`;
}

const resetStore = () => {
  useAdminStore.setState({
    adminAuthenticated: false,
    adminRole: null,
    adminError: '',
    actionStatus: '',
    adminSubTab: 'dashboard',
    adminEmail: '',
    otpRequired: false,
    adminOtp: '',
    rememberBrowser: false,
    totpSetupRequired: false,
    totpSecret: '',
    provisioningUri: '',
    recoveryCodes: [],
    recoveryCode: '',
  });
};

beforeEach(() => {
  vi.clearAllMocks();
  getAdminToken.mockReturnValue(null);
  resetStore();
});

describe('adminStore — initial state contract', () => {
  it('starts unauthenticated when no stored token exists', () => {
    // বাংলা: getAdminToken() → null → initial adminAuthenticated = false
    getAdminToken.mockReturnValue(null);
    expect(useAdminStore.getState().adminAuthenticated).toBe(false);
  });

  it('exposes the full state-contract keys', () => {
    const s = useAdminStore.getState();
    for (const key of [
      'adminAuthenticated',
      'adminRole',
      'adminError',
      'actionStatus',
      'adminSubTab',
      'adminEmail',
      'otpRequired',
      'adminOtp',
      'rememberBrowser',
      'totpSetupRequired',
      'totpSecret',
      'provisioningUri',
      'recoveryCodes',
      'recoveryCode',
    ] as const) {
      expect(s).toHaveProperty(key);
    }
    expect(s.adminSubTab).toBe('dashboard');
    expect(s.adminAuthenticated).toBe(false);
    expect(s.adminRole).toBeNull();
    expect(s.adminError).toBe('');
  });
});

describe('adminStore — setter contract', () => {
  it('setAdminRole / setAdminError / setActionStatus update state', () => {
    const s = useAdminStore.getState();
    s.setAdminRole('admin');
    s.setAdminError('boom');
    s.setActionStatus('saving');
    expect(useAdminStore.getState().adminRole).toBe('admin');
    expect(useAdminStore.getState().adminError).toBe('boom');
    expect(useAdminStore.getState().actionStatus).toBe('saving');
  });

  it('setAdminSubTab / setAdminEmail / setOtpRequired update state', () => {
    const s = useAdminStore.getState();
    s.setAdminSubTab('agents');
    s.setAdminEmail('x@y.com');
    s.setOtpRequired(true);
    expect(useAdminStore.getState().adminSubTab).toBe('agents');
    expect(useAdminStore.getState().adminEmail).toBe('x@y.com');
    expect(useAdminStore.getState().otpRequired).toBe(true);
  });

  it('setTotpSecret / setProvisioningUri / setRecoveryCode update state', () => {
    const s = useAdminStore.getState();
    s.setTotpSecret('SECRET23');
    s.setProvisioningUri('otpauth://totp/x');
    s.setRecoveryCode('rc-1');
    expect(useAdminStore.getState().totpSecret).toBe('SECRET23');
    expect(useAdminStore.getState().provisioningUri).toBe('otpauth://totp/x');
    expect(useAdminStore.getState().recoveryCode).toBe('rc-1');
  });
});

describe('adminStore — handleAdminLogin flow', () => {
  it('returns early when email/password missing and no otp stage', async () => {
    const s = useAdminStore.getState();
    await s.handleAdminLogin('   '); // খালি password
    expect(firebaseLogin).not.toHaveBeenCalled();
  });

  it('trusted_browser response → authenticated + admin role + token persisted', async () => {
    const token = makeJwt({ role: 'admin', exp: Math.floor(Date.now() / 1000) + 3600 });
    firebaseLogin.mockResolvedValue({ status: 'trusted_browser', token });
    const { signInWithEmailAndPassword } = await import('firebase/auth');
    (signInWithEmailAndPassword as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { getIdToken: async () => 'id-token-abc' },
    });

    useAdminStore.getState().setAdminEmail('admin@example.com');
    await useAdminStore.getState().handleAdminLogin('secret-password');

    const st = useAdminStore.getState();
    expect(st.adminAuthenticated).toBe(true);
    expect(st.adminRole).toBe('admin');
    expect(setAdminToken).toHaveBeenCalledWith(token);
    expect(updateTokenCache).toHaveBeenCalledWith(token);
  });

  it('non-admin role token → authenticated but adminRole null', async () => {
    const token = makeJwt({ role: 'viewer', exp: Math.floor(Date.now() / 1000) + 3600 });
    firebaseLogin.mockResolvedValue({ status: 'trusted_browser', token });
    const { signInWithEmailAndPassword } = await import('firebase/auth');
    (signInWithEmailAndPassword as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { getIdToken: async () => 'id-token-abc' },
    });

    useAdminStore.getState().setAdminEmail('viewer@example.com');
    await useAdminStore.getState().handleAdminLogin('secret-password');

    const st = useAdminStore.getState();
    expect(st.adminAuthenticated).toBe(true);
    expect(st.adminRole).toBeNull(); // role অবশ্যই admin নয় → null
  });

  it('otp_required response → otpRequired = true', async () => {
    firebaseLogin.mockResolvedValue({ status: 'otp_required' });
    const { signInWithEmailAndPassword } = await import('firebase/auth');
    (signInWithEmailAndPassword as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { getIdToken: async () => 'id-token-abc' },
    });

    useAdminStore.getState().setAdminEmail('admin@example.com');
    await useAdminStore.getState().handleAdminLogin('secret-password');
    expect(useAdminStore.getState().otpRequired).toBe(true);
  });

  it('totp_setup_required response → setup state + provisioning uri', async () => {
    firebaseLogin.mockResolvedValue({ status: 'totp_setup_required' });
    firebaseTotpSetup.mockResolvedValue({
      secret: 'SETUPSECRET',
      recovery_codes: ['rc1', 'rc2'],
      provisioning_uri: 'otpauth://totp/SupremeAI:admin%40example.com',
    });
    const { signInWithEmailAndPassword } = await import('firebase/auth');
    (signInWithEmailAndPassword as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { getIdToken: async () => 'id-token-abc' },
    });

    useAdminStore.getState().setAdminEmail('admin@example.com');
    await useAdminStore.getState().handleAdminLogin('secret-password');

    const st = useAdminStore.getState();
    expect(st.totpSetupRequired).toBe(true);
    expect(st.otpRequired).toBe(true);
    expect(st.totpSecret).toBe('SETUPSECRET');
    expect(st.recoveryCodes).toEqual(['rc1', 'rc2']);
    expect(st.provisioningUri).toContain('otpauth://totp/');
  });

  it('backend provisioning_uri না দিলে client-side otpauth URI বানায়', async () => {
    firebaseLogin.mockResolvedValue({ status: 'totp_setup_required' });
    firebaseTotpSetup.mockResolvedValue({ secret: 'FALLBACKSEC', recovery_codes: [] }); // uri নেই
    const { signInWithEmailAndPassword } = await import('firebase/auth');
    (signInWithEmailAndPassword as ReturnType<typeof vi.fn>).mockResolvedValue({
      user: { getIdToken: async () => 'id-token-abc' },
    });

    useAdminStore.getState().setAdminEmail('admin@example.com');
    await useAdminStore.getState().handleAdminLogin('secret-password');

    const uri = useAdminStore.getState().provisioningUri;
    expect(uri).toContain('otpauth://totp/SupremeAI:');
    expect(uri).toContain('secret=FALLBACKSEC');
  });
});

describe('adminStore — handleAdminLogout contract', () => {
  it('clears token storage and resets authenticated state', async () => {
    useAdminStore.setState({ adminAuthenticated: true, adminRole: 'admin', adminEmail: 'a@b.com' });
    await useAdminStore.getState().handleAdminLogout();
    const st = useAdminStore.getState();
    expect(clearAdminToken).toHaveBeenCalled();
    expect(st.adminAuthenticated).toBe(false);
  });
});
