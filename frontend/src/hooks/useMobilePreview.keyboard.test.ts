// useMobilePreview keyboard shortcut tests (#4138 Phase 1 follow-up)
// বাংলা: Ctrl+M শর্টকাটের চুক্তি — টগল করে, auto-repeat উপেক্ষা করে, এবং
// সবচেয়ে গুরুত্বপূর্ণ: cleanup ফেরত দেয়, কল করলে listener সত্যিই সরে যায়
// (আগের leak-বাগ: StrictMode double-mount-ে listener জমত, এক চাপে দুবার টগল)।

import { describe, it, expect, beforeEach } from 'vitest';
import { useMobilePreview, setupMobilePreviewKeyboard } from './useMobilePreview';

const pressCtrlM = () => {
  window.dispatchEvent(new KeyboardEvent('keydown', { key: 'm', ctrlKey: true, bubbles: true }));
};

describe('setupMobilePreviewKeyboard (Ctrl+M)', () => {
  beforeEach(() => {
    useMobilePreview.setState({ isOpen: false });
  });

  it('toggles the preview on Ctrl+M', () => {
    const cleanup = setupMobilePreviewKeyboard();
    expect(useMobilePreview.getState().isOpen).toBe(false);

    pressCtrlM();
    expect(useMobilePreview.getState().isOpen).toBe(true);
    pressCtrlM();
    expect(useMobilePreview.getState().isOpen).toBe(false);

    cleanup();
  });

  it('ignores auto-repeat (key held down)', () => {
    const cleanup = setupMobilePreviewKeyboard();

    const repeat = new KeyboardEvent('keydown', { key: 'm', ctrlKey: true, repeat: true });
    window.dispatchEvent(repeat);
    expect(useMobilePreview.getState().isOpen).toBe(false);

    cleanup();
  });

  it('cleanup removes the listener — no double-toggle after re-setup', () => {
    // বাংলা: আগের বাগ-পুনর্নির্মাণ — পুরনো কোডে প্রতি setup-এ anonymous listener
    // জমত; এখন cleanup করলে একটাই listener থাকে, এক চাপে ঠিক একবারই টগল।
    const cleanup1 = setupMobilePreviewKeyboard();
    cleanup1();
    const cleanup2 = setupMobilePreviewKeyboard();

    pressCtrlM();
    expect(useMobilePreview.getState().isOpen).toBe(true);

    // প্রথম (already-removed) listener আর সাড়া দিলে isOpen এখানে false হয়ে যেত।
    pressCtrlM();
    expect(useMobilePreview.getState().isOpen).toBe(false);

    cleanup2();
  });
});
