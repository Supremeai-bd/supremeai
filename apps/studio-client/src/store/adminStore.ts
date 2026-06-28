import { create } from 'zustand';

interface AdminState {
  adminAuthenticated: boolean;
  adminPassword: string;
  setAdminPassword: (val: string) => void;
  adminError: string;
  setAdminError: (val: string) => void;
  handleAdminLogin: () => Promise<void>;
  handleAdminLogout: () => void;
  actionStatus: string;
  setActionStatus: (val: string) => void;
  adminSubTab: string;
  setAdminSubTab: (tab: string) => void;
  otpRequired: boolean;
  setOtpRequired: (val: boolean) => void;
  adminOtp: string;
  setAdminOtp: (val: string) => void;
}

export const useAdminStore = create<AdminState>((set, get) => ({
  adminAuthenticated: true,
  adminPassword: '',
  setAdminPassword: (val) => set({ adminPassword: val }),
  adminError: '',
  setAdminError: (val) => set({ adminError: val }),
  actionStatus: '',
  setActionStatus: (val) => set({ actionStatus: val }),
  adminSubTab: 'command-center',
  setAdminSubTab: (tab) => set({ adminSubTab: tab }),
  otpRequired: false,
  setOtpRequired: (val) => set({ otpRequired: val }),
  adminOtp: '',
  setAdminOtp: (val) => set({ adminOtp: val }),
  handleAdminLogin: async () => {
    const { adminPassword, otpRequired, adminOtp } = get();
    if (!adminPassword.trim()) return;
    set({ adminError: '' });
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || '';
      if (!otpRequired) {
        const res = await fetch(`${API_BASE}/api/admin/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: adminPassword.trim() }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'otp_required') {
            set({ otpRequired: true });
          }
        } else {
          const data = await res.json();
          set({ adminError: data.detail || 'Invalid password.' });
        }
      } else {
        const res = await fetch(`${API_BASE}/api/admin/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: adminPassword.trim(), otp: adminOtp.trim() }),
        });
        if (res.ok) {
          const data = await res.json();
          set({ adminAuthenticated: true, otpRequired: false, adminOtp: '' });
          localStorage.setItem('supremeai_admin_token', data.token);
        } else {
          const data = await res.json();
          set({ adminError: data.detail || 'Invalid verification code.' });
        }
      }
    } catch (err: any) {
      set({ adminError: 'Connection failed: ' + err.message });
    }
  },
  handleAdminLogout: () => {
    localStorage.removeItem('supremeai_admin_token');
    set({ adminAuthenticated: false, adminPassword: '', otpRequired: false, adminOtp: '' });
  },
}));
