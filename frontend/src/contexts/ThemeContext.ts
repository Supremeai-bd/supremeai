import { createContext } from 'react';
import type { Theme} from './ThemeConstants';

// বাংলা মন্তব্য: ThemeContext এখানে সরাসরি ডিফাইন করা হয়েছে, যাতে ThemeProvider.tsx এ রেফ্রেশ সমস্যা না হয়
interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  /**
   * বাংলা (#4138 Phase 1 follow-up): নির্দিষ্ট থিমে সরাসরি যাওয়া — ThemePicker
   * dropdown থেকে ৮টি থিমের যেকোনো একটিতে সাইকেল ছাড়াই জাম্প করা যায়।
   * toggleTheme-এর মতোই persist + backend-sync + eventBus emit করে।
   */
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
