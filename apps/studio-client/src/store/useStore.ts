import { create } from "zustand";

// 🛡️ টাইপ-সেফ স্ট্যাটাস এবং মেসেজ ইন্টারফেস ডেফিনিশন
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

interface SupremeState {
  // Core Infrastructure States (BFF Architecture Ready)
  isServerOnline: boolean;
  sessionId: string | null;
  currentIdempotencyKey: string | null;
  isOrchestrating: boolean;
  
  // Clean Orchestration Context (No Plaintext API Keys!)
  chatHistory: ChatMessage[];
  activeTaskType: string;
  executionError: string | null;

  // Actions / Mutators
  setServerStatus: (online: boolean) => void;
  initializeSession: (id: string) => void;
  generateIdempotencyKey: () => string;
  addMessage: (message: Omit<ChatMessage, "id" | "timestamp">) => void;
  clearHistory: () => void;
  triggerOrchestration: (active: boolean, error?: string | null) => void;
}

export const useStore = create<SupremeState>((set) => ({
  // ── 📦 Core Infrastructure Default States ────────────────────────
  isServerOnline: false,
  sessionId: null,
  currentIdempotencyKey: null,
  isOrchestrating: false,
  chatHistory: [],
  activeTaskType: "general",
  executionError: null,

  // ── ⚡ Actions & Mutators (Zero Ghost State Architecture) ─────────
  
  setServerStatus: (online) => set({ isServerOnline: online }),

  initializeSession: (id) => set({ sessionId: id }),

  generateIdempotencyKey: () => {
    // 🔒 ডাবল-বিলিং এবং রেস কন্ডিশন ঠেকাতে প্রতি ক্লিকের জন্য ইউনিক UUIDv4 জেনারেটর
    const uniqueKey = crypto.randomUUID();
    set({ currentIdempotencyKey: uniqueKey });
    return uniqueKey;
  },

  addMessage: (message) => set((state) => ({
    chatHistory: [
      ...state.chatHistory,
      {
        ...message,
        id: crypto.randomUUID(),
        timestamp: Date.now()
      }
    ]
  })),

  clearHistory: () => set({ chatHistory: [], executionError: null }),

  triggerOrchestration: (active, error = null) => set({ 
    isOrchestrating: active, 
    executionError: error 
  })
}));
