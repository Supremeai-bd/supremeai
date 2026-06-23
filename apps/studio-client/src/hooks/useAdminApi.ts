// ============================================================================
// file >> useAdminApi.ts
// project >> SupremeAI 2.0
// purpose >> Admin panel and controls
// module >> src
// ============================================================================
const API_BASE = import.meta.env.VITE_API_BASE || '';

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) throw new Error(`Failed: ${url}`);
  return res.json();
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail || 'Request failed');
  return res.json();
}

async function delJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Delete failed');
  return res.json();
}

export function useAdminRules() {
  return useQuery({
    queryKey: ['admin', 'rules'],
    queryFn: () => fetchJSON<any>('/admin/rules'),
  });
}

export function useSaveRules() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rules: unknown) => postJSON('/admin/rules', { rules }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'rules'] }),
  });
}

export function useSkills(query = '') {
  return useQuery({
    queryKey: ['skills', query],
    queryFn: () => postJSON<import('../types').Skill[]>('/api/skills/search', { query, installed_only: false }),
  });
}

export function useInstallSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (skill: string) => postJSON(`/api/skills/install`, { skill }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });
}

export function useCheckpoints() {
  return useQuery({
    queryKey: ['checkpoints'],
    queryFn: () => fetchJSON<import('../types').Checkpoint[]>('/memory/checkpoints'),
  });
}

export function useDeleteCheckpoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => delJSON(`/memory/checkpoint/${taskId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['checkpoints'] }),
  });
}

export function useCostReport() {
  return useQuery({
    queryKey: ['costs'],
    queryFn: () => fetchJSON<{ report: string }>('/admin-api/costs'),
    refetchInterval: 60000,
  });
}

export function useHealthMap() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => fetchJSON<any>('/admin-api/health-map'),
    refetchInterval: 30000,
  });
}

export function useAdminUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => fetchJSON<any[]>('/admin-api/users'),
  });
}

export function useSaveUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (user: { username: string; role: string; permissions: string[] }) =>
      postJSON('/admin-api/users', user),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (username: string) => delJSON(`/admin-api/users/${username}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useEnvConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: () => fetchJSON<Record<string, string>>('/admin-api/config'),
  });
}

export function useSaveConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (env_vars: Record<string, string>) => postJSON('/admin-api/config', { env_vars }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config'] }),
  });
}

export function useTriggerDeploy() {
  return useMutation({
    mutationFn: () => postJSON<{ message: string }>('/admin-api/deploy', {}),
  });
}

export function useGcpHealth() {
  return useQuery({
    queryKey: ['gcp', 'health'],
    queryFn: () => fetchJSON<import('../types').GcpHealth>('/gcp/health'),
    refetchInterval: 30000,
  });
}

export function useCloudStats() {
  return useQuery({
    queryKey: ['cloud', 'distribution'],
    queryFn: () => fetchJSON<import('../types').CloudStats>('/admin/cloud-distribution'),
    refetchInterval: 30000,
  });
}
