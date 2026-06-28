// Centralized API Client for SupremeAI 2.0
// বাংলা মন্তব্য: এটি অ্যাপ্লিকেশনের সেন্ট্রাল এপিআই ক্লায়েন্ট যা হেডার ও টোকেন ম্যানেজ করে।

const API_BASE_URL = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('supremeai_admin_token') || localStorage.getItem('token') || '';
  return {
    'Content-Type': 'application/json',
    'Authorization': token ? `Bearer ${token}` : '',
  };
};

export const apiClient = {
  get: async <T>(path: string, options?: RequestInit): Promise<T> => {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'GET',
      headers: getAuthHeaders(),
      ...options,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'API request failed' }));
      throw new Error(errData.detail || `HTTP error! status: ${res.status}`);
    }
    return res.json();
  },

  post: async <T>(path: string, body?: any, options?: RequestInit): Promise<T> => {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'API request failed' }));
      throw new Error(errData.detail || `HTTP error! status: ${res.status}`);
    }
    return res.json();
  },

  put: async <T>(path: string, body?: any, options?: RequestInit): Promise<T> => {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'API request failed' }));
      throw new Error(errData.detail || `HTTP error! status: ${res.status}`);
    }
    return res.json();
  },

  delete: async <T>(path: string, options?: RequestInit): Promise<T> => {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
      ...options,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'API request failed' }));
      throw new Error(errData.detail || `HTTP error! status: ${res.status}`);
    }
    return res.json();
  },
};
