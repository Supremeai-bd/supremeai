// Chat API Service for SupremeAI 2.0
// বাংলা মন্তব্য: চ্যাট ইন্টারফেস ও স্ট্রিমিং এপিআই এর সাথে যোগাযোগের জন্য ব্যবহৃত সার্ভিস।

import { apiClient } from './apiClient';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatResponse {
  response: string;
  tokens_used?: number;
  provider?: string;
  duration?: number;
}

export const chatService = {
  sendMessage: async (message: string, history: ChatMessage[] = []): Promise<ChatResponse> => {
    return apiClient.post<ChatResponse>('/api/task/execute', {
      message,
      history,
    });
  },

  getVoices: async (): Promise<any[]> => {
    return apiClient.get<any[]>('/api/voice/voices');
  },
};
