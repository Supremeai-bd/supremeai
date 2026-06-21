import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { CustomerState } from '../types/customer';

const STORAGE_KEY = 'supremeai_customer_state';

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
      storage: createJSONStorage(() => localStorage),
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
