// Agent Operations Service for SupremeAI 2.0
// বাংলা মন্তব্য: এজেন্ট ডিপার্টমেন্ট, টাস্ক এক্সেকিউশন ও এজেন্টদের তথ্য আনার জন্য ব্যবহৃত সার্ভিস।

import { apiClient } from './apiClient';

export interface AgentTask {
  id: string;
  name: string;
  status: string;
  result?: string;
}

export const agentService = {
  executeAgentTask: async (agentId: string, instruction: string): Promise<AgentTask> => {
    return apiClient.post<AgentTask>(`/api/agent/${agentId}/execute`, {
      instruction,
    });
  },

  listAgents: async (): Promise<any[]> => {
    return apiClient.get<any[]>('/api/agents');
  },

  getAgentStatus: async (agentId: string): Promise<{ status: string }> => {
    return apiClient.get<{ status: string }>(`/api/agent/${agentId}/status`);
  },
};
