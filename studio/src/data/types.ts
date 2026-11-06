export type CommandModuleId = string;

export interface HealthNode {
  id?: string;
  name?: string;
  status?: string;
  health?: number;
  latency_ms?: number;
  [key: string]: unknown;
}

export interface Provider {
  id?: string;
  name?: string;
  status?: string;
  latency_ms?: number;
  models?: string[];
  [key: string]: unknown;
}

export interface Agent {
  id?: string;
  name?: string;
  status?: string;
  queue_depth: number;
  [key: string]: unknown;
}

export interface Tenant {
  id?: string;
  name?: string;
  status?: string;
  [key: string]: unknown;
}

export interface User {
  id?: string;
  email?: string;
  name?: string;
  role?: string;
  [key: string]: unknown;
}

export interface SecurityFinding {
  id?: string;
  title?: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  status?: string;
  [key: string]: unknown;
}

export interface ThreatScanResult {
  status?: string;
  scanned_at?: string;
  findings?: number;
  [key: string]: unknown;
}

export interface DashboardEvent {
  id?: string;
  timestamp?: string;
  level?: string;
  message?: string;
  [key: string]: unknown;
}
