export interface ChatMessage {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  timestamp: string;
}

export interface Skill {
  id: string;
  name: string;
  version: string;
  description: string;
  dependencies?: string;
  installed: boolean;
  source: string;
}

export interface Checkpoint {
  task_id: string;
  step_index: number;
  state: Record<string, any>;
}

export interface CloudStats {
  distribution: Record<string, any>;
  total_requests: number;
  active_providers: number;
  strategy: string;
}

export interface GcpHealth {
  status: string;
  cloud_run: any;
  firestore_mode: string;
  pubsub_mode: string;
  cloud_functions: any;
}

export interface HealthMap {
  gcp: { status: string; latency: string; region: string };
  railway: { status: string; latency: string; region: string };
  render: { status: string; latency: string; region: string };
}

export interface AdminUser {
  username: string;
  role: string;
  permissions: string[];
}

export type AdminSubTab = 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'command-center' | 'model-router' | 'skills' | 'memory' | 'cloud' | 'observability' | 'threats' | 'rules' | 'cicd' | 'github' | 'backups' | 'rate-limits';
