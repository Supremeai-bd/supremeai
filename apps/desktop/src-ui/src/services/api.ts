import { fetch } from '@tauri-apps/api/http';

const API_BASE = import.meta.env.VITE_API_BASE || 'https://api.supremeai.dev';

const getAuthHeaders = (includeJson = false) => {
  const token = localStorage.getItem('jwt');
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (includeJson) {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
};

export const supremeApi = {
  login: (token: string) => {
    localStorage.setItem('jwt', token);
  },

  sendMessage: async (message: string) => {
    return await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: getAuthHeaders(true),
      body: JSON.stringify({ message }),
    });
  },

  listSkills: async () => {
    return await fetch(`${API_BASE}/api/skills`, {
      headers: getAuthHeaders(),
    });
  },

  executeSkill: async (name: string, params: any) => {
    return await fetch(`${API_BASE}/api/skills/${name}/execute`, {
      method: 'POST',
      headers: getAuthHeaders(true),
      body: JSON.stringify(params),
    });
  },

  forgeSkill: async (demand: string) => {
    return await fetch(`${API_BASE}/api/evolution/forge`, {
      method: 'POST',
      headers: getAuthHeaders(true),
      body: JSON.stringify({ skill_name: demand, user_demand: demand }),
    });
  },

  connectRepo: async (url: string) => {
    return await fetch(`${API_BASE}/api/github/connect`, {
      method: 'POST',
      headers: getAuthHeaders(true),
      body: JSON.stringify({ repo_url: url }),
    });
  },

  getLogs: async () => {
    return await fetch(`${API_BASE}/admin-api/logs/stream`, {
      headers: getAuthHeaders(),
    });
  },

  getCosts: async () => {
    return await fetch(`${API_BASE}/admin-api/costs`, {
      headers: getAuthHeaders(),
    });
  },
};
