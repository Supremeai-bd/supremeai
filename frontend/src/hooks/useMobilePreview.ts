/**
 * Mobile preview state management (#4148).
 *
 * বাংলা: মোবাইল প্রিভিউয়ের state — Zustand store (existing convention)।
 * localStorage-এ persist করা নিষিদ্ধ (UI অবস্থা, সেটিংস নয়) — useMobileNav-এর
 * pattern follow করে।
 *
 * Keyboard shortcut: Ctrl+M toggles mobile preview.
 */

import { create } from 'zustand';

export type Orientation = 'portrait' | 'landscape';

interface MobilePreviewState {
  /** Whether the mobile preview panel is visible. */
  isOpen: boolean;
  /** Selected device preset ID. */
  deviceId: string;
  /** Current orientation. */
  orientation: Orientation;
  /** Custom device width (when deviceId === 'custom'). */
  customWidth: number;
  /** Custom device height (when deviceId === 'custom'). */
  customHeight: number;

  // Actions
  toggle: () => void;
  setOpen: (open: boolean) => void;
  setDevice: (deviceId: string) => void;
  setOrientation: (orientation: Orientation) => void;
  toggleOrientation: () => void;
  setCustomDimensions: (width: number, height: number) => void;
}

export const useMobilePreview = create<MobilePreviewState>((set) => ({
  isOpen: false,
  deviceId: 'iphone15',
  orientation: 'portrait',
  customWidth: 375,
  customHeight: 667,

  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  setOpen: (open) => set({ isOpen: open }),
  setDevice: (deviceId) => set({ deviceId }),
  setOrientation: (orientation) => set({ orientation }),
  toggleOrientation: () =>
    set((state) => ({
      orientation: state.orientation === 'portrait' ? 'landscape' : 'portrait',
    })),
  setCustomDimensions: (width, height) =>
    set({ customWidth: Math.max(100, width), customHeight: Math.max(100, height) }),
}));

/**
 * Keyboard shortcut handler — Ctrl+M toggles mobile preview.
 * বাংলা: Ctrl+M চাপলে মোবাইল প্রিভিউ toggle হয়।
 */
export function setupMobilePreviewKeyboard() {
  if (typeof window === 'undefined') return;

  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'm' && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      useMobilePreview.getState().toggle();
    }
  });
}
