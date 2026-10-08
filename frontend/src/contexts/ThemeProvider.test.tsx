import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { ThemeProvider } from './ThemeProvider';
import { useTheme } from './useTheme';

// Test consumer component
const TestThemeConsumer: React.FC = () => {
  const { theme, toggleTheme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <button data-testid="toggle-btn" onClick={toggleTheme}>
        Toggle
      </button>
      <button data-testid="set-btn" onClick={() => setTheme('emerald')}>
        Set Emerald
      </button>
    </div>
  );
};

describe('ThemeProvider (Issue #494)', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = '';
    document.documentElement.removeAttribute('data-theme');
    document.body.className = '';
    document.body.removeAttribute('data-theme');
    vi.clearAllMocks();
  });

  it('initializes with default dark theme and applies DOM classes', () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(document.body.classList.contains('dark')).toBe(true);
    expect(document.body.getAttribute('data-theme')).toBe('dark');
  });

  it('cycles across all 8 themes in order: dark -> light -> synthwave -> cyberpunk -> minimal -> sunset -> matrix -> emerald -> dark', async () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    const toggleBtn = screen.getByTestId('toggle-btn');
    const themeSpan = screen.getByTestId('current-theme');

    // (#4138): 8-থিম সাইকেল — THEME_ORDER-ই SSOT; টেস্ট সেটাই মেনে চলে।
    const expected: Array<[string, string]> = [
      ['light', 'light'],
      ['synthwave', 'synthwave'],
      ['cyberpunk', 'cyberpunk'],
      ['minimal', 'minimal'],
      ['sunset', 'sunset'],
      ['matrix', 'matrix'],
      ['emerald', 'emerald'],
      ['dark', 'dark'], // পূর্ণ পরিক্রমা শেষে আবার শুরু
    ];

    for (const [themeName, className] of expected) {
      await act(async () => {
        fireEvent.click(toggleBtn);
      });
      expect(themeSpan).toHaveTextContent(themeName);
      expect(document.documentElement.classList.contains(className)).toBe(true);
      expect(document.documentElement.getAttribute('data-theme')).toBe(themeName);
    }
  });

  it('persists selected theme in localStorage', async () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    const toggleBtn = screen.getByTestId('toggle-btn');
    await act(async () => {
      fireEvent.click(toggleBtn);
    });

    const stored = localStorage.getItem('supremeai-theme-storage');
    expect(stored).toBeTruthy();
    expect(JSON.parse(stored!).state.theme).toBe('light');
  });

  it('(#4138 follow-up) setTheme jumps directly to a theme, persists and syncs the DB', async () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId('set-btn'));
    });

    // বাংলা: সাইকেল ছাড়াই সরাসরি emerald — dark → light → … (৭ চাপ) লাগে না।
    expect(screen.getByTestId('current-theme')).toHaveTextContent('emerald');
    expect(document.documentElement.getAttribute('data-theme')).toBe('emerald');
    expect(document.body.classList.contains('emerald')).toBe(true);

    const stored = localStorage.getItem('supremeai-theme-storage');
    expect(stored).toBeTruthy();
    expect(JSON.parse(stored!).state.theme).toBe('emerald');
  });

  it('(#4138 follow-up) setTheme ignores unknown theme names (fail-safe)', async () => {
    // বাংলা: অজানা মান (যেমন legacy/ভাঙা localStorage থেকে) এলে থিম অপরিবর্তিত থাকে।
    const InvalidSetter: React.FC = () => {
      const { setTheme } = useTheme();
      return (
        <button data-testid="invalid-btn" onClick={() => setTheme('not-a-theme' as never)}>
          Set Invalid
        </button>
      );
    };

    render(
      <ThemeProvider>
        <TestThemeConsumer />
        <InvalidSetter />
      </ThemeProvider>
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId('invalid-btn'));
    });

    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
});
