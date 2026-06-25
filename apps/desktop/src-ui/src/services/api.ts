// src-ui/src/services/api.ts
import { fetch } from '@tauri-apps/plugin-http';

const API_BASE = import.meta.env.VITE_API_BASE || 'https://api.supremeai.dev';

export const supremeApi = {
  // Auth
  login: (token: string) => {
    localStorage.setItem('jwt', token);
  },

  // Chat
  sendMessage: async (message: string) => {
    const token = localStorage.getItem('jwt');
    return await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ message })
    });
  },

  listSkills: async () => {
    const token = localStorage.getItem('jwt');
    return await fetch(`${API_BASE}/api/skills`, {
      headers: { 
        'Authorization': `Bearer ${token}` 
      }
    });
  },
  executeSkill: async (name: string, params: any) => {
    const token = localStorage.getItem('jwt');
    return await fetch(`${API_BASE}/api/skills/${name}/execute`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(params)
    });
  },

  forgeSkill: async (demand: string) => {
    const token = localStorage.getItem('jwt');
    return await fetch(`${API_BASE}/api/evolution/forge`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ skill_name: demand, user_demand: demand })
    });
  },

  connectRepo: async (url: string) => {
    const token = localStorage.getItem('jwt');
    return await fetch(`${API_BASE}/api/github/connect`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ repo_url: url })
    });
  },

  getLogs: async () => {
    const token = localStorage.getItem('jwt');
    return await fetch(`${API_BASE}/admin-api/logs/stream`, {
      headers: { 
        'Authorization': `Bearer ${token}` 
      }
    });
  },
  getCosts: async () => {
    const token = localStorage.getItem('jwt');
    return await fetch(`${API_BASE}/admin-api/costs`, {
      headers: { 
        'Authorization': `Bearer ${token}` 
      }
    });
  },
};