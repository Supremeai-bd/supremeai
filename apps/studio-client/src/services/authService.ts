// Authentication Service for SupremeAI 2.0
// বাংলা মন্তব্য: এটি অ্যাডমিন লগইন ও ফায়ারবেস অথেন্টিকেশন সার্ভিস প্রোভাইড করে।

import { apiClient } from './apiClient';

export const authService = {
  adminLogin: async (password: string): Promise<{ status: string; message?: string }> => {
    return apiClient.post<{ status: string; message?: string }>('/api/admin/login', { password });
  },

  adminVerifyOtp: async (password: string, otp: string): Promise<{ status: string; token: string }> => {
    return apiClient.post<{ status: string; token: string }>('/api/admin/verify', { password, otp });
  },

  firebaseLogin: async (idToken: string): Promise<{ status: string; token?: string; uid?: string; email?: string }> => {
    return apiClient.post<{ status: string; token?: string; uid?: string; email?: string }>('/api/admin/firebase-login', { id_token: idToken });
  },

  firebaseTotpSetup: async (idToken: string): Promise<{ secret: string; provisioning_uri: string }> => {
    return apiClient.post<{ secret: string; provisioning_uri: string }>('/api/admin/firebase-totp-setup', { id_token: idToken });
  },

  firebaseTotpVerify: async (idToken: string, otp: string): Promise<{ status: string; token: string }> => {
    return apiClient.post<{ status: string; token: string }>('/api/admin/firebase-totp-verify', { id_token: idToken, otp });
  },

  easyLogin: async (code: string): Promise<{ status: string; token: string }> => {
    return apiClient.post<{ status: string; token: string }>('/api/admin/easy-login', { code });
  },
};
