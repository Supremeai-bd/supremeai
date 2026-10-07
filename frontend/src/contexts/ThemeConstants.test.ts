// (#4138 Phase 1) ThemeConstants-চুক্তি — 8-থিম SSOT-এর presence-contract।
// বাংলা মন্তব্য: THEME_ORDER/THEME_META-ই থিম-জগতের একমাত্র উৎস। এই টেস্ট
// ৮-থিম চুক্তি + প্রতিটি থিমের মেটা-আস্তিত্ব + isDarkTheme fail-safe
// — কেউ SSOT ভাঙলে (থিম বাদ/ডুপ্লিকেট) PR-gate লাল দেখাবে।
import { describe, it, expect } from 'vitest';
import { THEME_ORDER, THEME_META, isDarkTheme, type Theme } from './ThemeConstants';

describe('ThemeConstants (#4138 — 8-theme contract)', () => {
  it('THEME_ORDER declares exactly the 8 themes of MASTER_PLAN_V2', () => {
    expect(THEME_ORDER).toHaveLength(8);
    expect(THEME_ORDER).toEqual(
      expect.arrayContaining([
        'dark', 'light', 'synthwave', 'cyberpunk', 'minimal', 'sunset', 'matrix', 'emerald',
      ]),
    );
  });

  it('THEME_ORDER contains no duplicates', () => {
    expect(new Set(THEME_ORDER).size).toBe(THEME_ORDER.length);
  });

  it('THEME_META covers every theme with a label and a boolean isDark', () => {
    for (const theme of THEME_ORDER) {
      const meta = THEME_META[theme as Theme];
      expect(meta, `THEME_META missing entry for '${theme}'`).toBeDefined();
      expect(typeof meta.label).toBe('string');
      expect(meta.label.length).toBeGreaterThan(0);
      expect(typeof meta.isDark).toBe('boolean');
    }
  });

  it('light-family themes (light, minimal) are marked isDark=false, rest true', () => {
    expect(THEME_META.light.isDark).toBe(false);
    expect(THEME_META.minimal.isDark).toBe(false);
    for (const theme of ['dark', 'synthwave', 'cyberpunk', 'sunset', 'matrix', 'emerald'] as Theme[]) {
      expect(THEME_META[theme].isDark, `${theme} should be dark-family`).toBe(true);
    }
  });

  it('isDarkTheme returns the meta verdict and fails safe (true) on unknown values', () => {
    expect(isDarkTheme('synthwave')).toBe(true);
    expect(isDarkTheme('minimal')).toBe(false);
    // fail-safe: অজানা/দূষিত মান ডার্ক-আচরণ ধরে — লাইট-ডিফল্টে ডার্ক-UI ভাঙবে না।
    expect(isDarkTheme('nope' as Theme)).toBe(true);
    expect(isDarkTheme('' as Theme)).toBe(true);
  });
});
