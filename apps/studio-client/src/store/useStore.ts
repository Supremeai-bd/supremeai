import { create } from "zustand";

const API_BASE_URL = import.meta.env.VITE_API_BASE || "http://localhost:8000";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

interface DeployGateInfo {
  status: "LOCKED" | "UNLOCKED";
  reason: string;
  updated_at?: string;
}

interface EvolutionState {
  isForging: boolean;
  forgeFeedback: string | null;
  forgeSuccessCode: string | null;
  
  // ⚡ Evolution Action
  forgeNewSkill: (skillName: string, userDemand: string) => Promise<void>;
}

interface SupremeState extends EvolutionState {
  isServerOnline: boolean;
  sessionId: string | null;
  currentIdempotencyKey: string | null;
  isOrchestrating: boolean;
  chatHistory: ChatMessage[];
  activeTaskType: string;
  executionError: string | null;
  streamLogs: string[];
  
  // 🛡️ New Autonomous Gate States
  deployGate: DeployGateInfo | null;
  isGateLoading: boolean;

  setServerStatus: (online: boolean) => void;
  initializeSession: (id: string) => void;
  generateIdempotencyKey: () => string;
  addMessage: (message: Omit<ChatMessage, "id" | "timestamp">) => void;
  clearHistory: () => void;
  triggerOrchestration: (active: boolean, error?: string | null) => void;
  
  // ⚡ New Gate Actions
  fetchGateStatus: () => Promise<void>;
  executeGateOverride: (targetStatus: string, reason: string, secret: string) => Promise<{ success: boolean; message: string }>;
}

export const useStore = create<SupremeState>((set) => ({
  isServerOnline: false,
  sessionId: null,
  currentIdempotencyKey: null,
  isOrchestrating: false,
  chatHistory: [],
  activeTaskType: "general",
  executionError: null,
  streamLogs: [],
  
  // Default States
  deployGate: null,
  isGateLoading: false,

  isForging: false,
  forgeFeedback: null,
  forgeSuccessCode: null,

  setServerStatus: (online) => set({ isServerOnline: online }),
  initializeSession: (id) => set({ sessionId: id }),
  generateIdempotencyKey: () => {
    const uniqueKey = crypto.randomUUID();
    set({ currentIdempotencyKey: uniqueKey });
    return uniqueKey;
  },
  addMessage: (message) => set((state) => ({
    chatHistory: [...state.chatHistory, { ...message, id: crypto.randomUUID(), timestamp: Date.now() }]
  })),
  clearHistory: () => set({ chatHistory: [], executionError: null }),
  triggerOrchestration: (active, error = null) => set({ isOrchestrating: active, executionError: error }),

  // ── 🛡️ Autonomous Gate Management Actions ────────────────────────
  fetchGateStatus: async () => {
    set({ isGateLoading: true });
    try {
      // আমরা যে গেটকিপার ফায়ারস্টোর ডাটা বানিয়েছি তা চেক করার এন্ডপয়েন্ট (অথবা কাস্টম গেট রুট)
      const res = await fetch(`${API_BASE_URL}/api/admin/metrics/dashboard`);
      if (res.ok) {
        const data = await res.json();
        // ড্যাশবোর্ড ম্যাট্রিক্স থেকে গেট ডাটা এক্সট্রাক্ট (ফলব্যাকসহ)
        set({ deployGate: { 
          status: data.status === "HEALTHY" ? "UNLOCKED" : "LOCKED", 
          reason: data.error || "System operating within safe deployment thresholds."
        }});
      }
    } catch (err) {
      console.error("Failed to sync deploy gate telemetry:", err);
    } finally {
      set({ isGateLoading: false });
    }
  },

  executeGateOverride: async (targetStatus, reason, secret) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/gate/override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_status: targetStatus,
          reason: reason,
          admin_secret: secret
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        set({ deployGate: { status: data.forced_status, reason: `👑 Forced: ${reason}` } });
        return { success: true, message: data.message };
      }
        return { success: false, message: data.detail || "Override verification rejected." };
    } catch (err: any) {
      return { success: false, message: err.message || "Network isolation error." };
    }
  },

  forgeNewSkill: async (skillName, userDemand) => {
    set({ isForging: true, forgeFeedback: "🧠 Self-Evolution Core is structuring your request...", forgeSuccessCode: null });
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/evolution/forge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skill_name: skillName, user_demand: userDemand })
      });
      
      const data = await res.json();
      
      if (res.ok && data.success) {
        set({ 
          isForging: false, 
          forgeFeedback: `🏆 Success! Skill '${data.skill_name}' is fully deployed to Firestore.`,
          forgeSuccessCode: data.generated_code // যদি ব্যাকএন্ড কোড রিটার্ন করে, তা স্ক্রিনে দেখানোর জন্য
        });
      } else {
        set({ 
          isForging: false, 
          forgeFeedback: `🚨 Evolution Blocked: ${data.detail || data.error || "Sandbox Verification Failed."}` 
        });
      }
    } catch (err: any) {
      set({ 
        isForging: false, 
        forgeFeedback: `❌ Infrastructure Error: ${err.message || "Network Failure."}` 
      });
    }
  }
}));
