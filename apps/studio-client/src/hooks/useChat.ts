import { useState, useCallback, useRef, useEffect } from 'react';
import { useStore } from '../store/useStore';
import { useCustomerStore } from '../store/customerStore';
import type { ChatMessage } from '../types/customer';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

interface UseChatOptions {
  projectId?: string;
  streaming?: boolean;
}

interface UseChatReturn {
  messages: ChatMessage[];
  input: string;
  setInput: (val: string) => void;
  send: () => Promise<void>;
  loading: boolean;
  error: string | null;
  clear: () => void;
}

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const { projectId, streaming = true } = options;
  const { addMessage: addCustomerMessage } = useCustomerStore();
  const { addMessage: addStoreMessage, triggerOrchestration } = useStore();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const send = useCallback(async () => {
    if (!input.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
      project_id: projectId,
    };

    setMessages(prev => [...prev, userMsg]);
    addCustomerMessage(userMsg);
    addStoreMessage({ role: 'user', content: input.trim() });
    setInput('');
    setLoading(true);
    setError(null);
    triggerOrchestration(true);

    if (streaming) {
      abortRef.current = new AbortController();

      try {
        const res = await fetch(`${API_BASE}/api/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userMsg.content,
            project_id: projectId,
            idempotency_key: crypto.randomUUID(),
          }),
          signal: abortRef.current.signal,
        });

        if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();
        let assistantContent = '';
        const assistantId = crypto.randomUUID();

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            assistantContent += chunk;

            const partialMsg: ChatMessage = {
              id: assistantId,
              role: 'assistant',
              content: assistantContent,
              timestamp: new Date().toISOString(),
              project_id: projectId,
            };

            setMessages(prev => {
              const existing = prev.findIndex(m => m.id === assistantId);
              if (existing >= 0) {
                const updated = [...prev];
                updated[existing] = partialMsg;
                return updated;
              }
              return [...prev, partialMsg];
            });
          }
        }

        const finalMsg: ChatMessage = {
          id: assistantId,
          role: 'assistant',
          content: assistantContent || 'No response received.',
          timestamp: new Date().toISOString(),
          project_id: projectId,
        };

        addCustomerMessage(finalMsg);
        addStoreMessage({ role: 'assistant', content: finalMsg.content });
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Unknown error occurred');
        }
      } finally {
        setLoading(false);
        triggerOrchestration(false);
        abortRef.current = null;
      }
    } else {
      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userMsg.content,
            project_id: projectId,
          }),
        });

        if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);

        const data = await res.json();
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: data.response || data.message || 'No response received.',
          timestamp: new Date().toISOString(),
          project_id: projectId,
          metadata: { model: data.model, tokens: data.tokens },
        };

        setMessages(prev => [...prev, assistantMsg]);
        addCustomerMessage(assistantMsg);
        addStoreMessage({ role: 'assistant', content: assistantMsg.content });
      } catch (err: any) {
        setError(err.message || 'Unknown error occurred');
      } finally {
        setLoading(false);
        triggerOrchestration(false);
      }
    }
  }, [input, loading, projectId, streaming, addCustomerMessage, addStoreMessage, triggerOrchestration]);

  const clear = useCallback(() => {
    setMessages([]);
    setInput('');
    setError(null);
  }, []);

  return { messages, input, setInput, send, loading, error, clear };
}
