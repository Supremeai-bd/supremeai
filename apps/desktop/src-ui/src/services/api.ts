import { fetch } from '@tauri-apps/api/http';

export class ApiError extends Error {
  status: number;
  body?: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

interface Skill {
  name: string;
  description?: string;
}

interface SendMessageResponse {
  response: string;
}

interface ListSkillsResponse {
  skills: Skill[];
}

interface ForgeSkillResponse {
  skill: { name: string };
}

interface ConnectRepoResponse {
  connected: boolean;
}

interface CostsResponse {
  total: number;
  breakdown: Record<string, number>;
}

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

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

async function request<T>(
  url: string,
  options: Record<string, unknown> = {}
): Promise<T> {
  const response = await fetch(url, {
    method: ((options.method as string) || 'GET') as 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
    ...options,
    headers: { ...getAuthHeaders(Boolean(options.method)), ...(options.headers || {}) },
  });
  const res = response as unknown as Record<string, unknown>;

  if (!res.ok) {
    let body: unknown;
    try {
      body = await (res as { json: () => Promise<unknown> }).json();
    } catch {
      body = undefined;
    }
    throw new ApiError(
      Number(res.status),
      `HTTP ${res.status}: ${(res.statusText as string) || 'Request failed'}`,
      body
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await (res as { json: () => Promise<T> }).json()) as T;
}

export const supremeApi = {
  login: (token: string) => {
    localStorage.setItem('jwt', token);
  },

  sendMessage: async (message: string) => {
    return request<SendMessageResponse>(`${API_BASE}/api/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },

  listSkills: async () => {
    return request<ListSkillsResponse>(`${API_BASE}/api/skills`);
  },

  executeSkill: async <T = unknown>(name: string, params: object) => {
    return request<T>(`${API_BASE}/api/skills/${name}/execute`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  forgeSkill: async (demand: string) => {
    return request<ForgeSkillResponse>(`${API_BASE}/api/evolution/forge`, {
      method: 'POST',
      body: JSON.stringify({ skill_name: demand, user_demand: demand }),
    });
  },

  connectRepo: async (url: string) => {
    return request<ConnectRepoResponse>(`${API_BASE}/api/github/connect`, {
      method: 'POST',
      body: JSON.stringify({ repo_url: url }),
    });
  },

  getLogs: async () => {
    return request<LogEntry[]>(`${API_BASE}/admin-api/logs/stream`);
  },

  getCosts: async () => {
    return request<CostsResponse>(`${API_BASE}/admin-api/costs`);
  },
};
