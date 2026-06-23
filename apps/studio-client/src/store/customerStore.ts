import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { CustomerState } from '../types/customer';

const STORAGE_KEY = 'supremeai_customer_state';
const ENCRYPTION_KEY = 'supremeai_god_salt_key_2026';

function encrypt(text: string): string {
  let result = '';
  for (let i = 0; i < text.length; i++) {
    result += String.fromCharCode(text.charCodeAt(i) ^ ENCRYPTION_KEY.charCodeAt(i % ENCRYPTION_KEY.length));
  }
  // Convert binary string to Base64 safely in browser environment
  return btoa(unescape(encodeURIComponent(result)));
}

function decrypt(encoded: string): string {
  try {
    const text = decodeURIComponent(escape(atob(encoded)));
    let result = '';
    for (let i = 0; i < text.length; i++) {
      result += String.fromCharCode(text.charCodeAt(i) ^ ENCRYPTION_KEY.charCodeAt(i % ENCRYPTION_KEY.length));
    }
    return result;
  } catch (e) {
    return '';
  }
}

const secureStorage = {
  getItem: (name: string): string | null => {
    const value = localStorage.getItem(name);
    if (!value) return null;
    return decrypt(value);
  },
  setItem: (name: string, value: string): void => {
    localStorage.setItem(name, encrypt(value));
  },
  removeItem: (name: string): void => {
    localStorage.removeItem(name);
  }
};

interface CustomerStoreState extends CustomerState {
  hydrated: boolean;
  setHydrated: (val: boolean) => void;
}

export const useCustomerStore = create<CustomerStoreState>()(
  persist(
    (set) => ({
      user: null,
      projects: [],
      activeProjectId: null,
      chatHistory: [],
      widgets: [],
      sidebarCollapsed: false,
      isLoading: false,
      hydrated: false,

      setUser: (user) => set({ user }),
      setProjects: (projects) => set({ projects }),
      setActiveProject: (id) => set({ activeProjectId: id }),
      addMessage: (message) =>
        set((state) => ({
          chatHistory: [...state.chatHistory, message],
        })),
      clearChat: () => set({ chatHistory: [] }),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      reorderWidgets: (widgets) => set({ widgets }),
      setHydrated: (val) => set({ hydrated: val }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => secureStorage),
      partialize: (state) => ({
        user: state.user,
        projects: state.projects,
        activeProjectId: state.activeProjectId,
        widgets: state.widgets,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
    }
  )
);

export function useHydrated() {
  return useCustomerStore((s) => s.hydrated);
}
