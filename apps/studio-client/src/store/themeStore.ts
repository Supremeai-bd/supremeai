// ============================================================================
// file >> themeStore.ts
// project >> SupremeAI 2.0
// purpose >> State management
// module >> src
// ============================================================================
import { persist, createJSONStorage } from 'zustand/middleware';

interface ThemeState {
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: 'dark',
      toggleTheme: () => set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),
    }),
    {
      name: 'supremeai-theme-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
