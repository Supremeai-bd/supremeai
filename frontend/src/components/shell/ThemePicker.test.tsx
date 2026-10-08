// ThemePicker tests (#4138 Phase 1 follow-up)
// বাংলা: ৮-থিম dropdown-এর চুক্তি — SSOT (THEME_META/THEME_ORDER) থেকে মেনু
// আঁকে, সক্রিয় থিম aria-checked, ক্লিকে setTheme কল ও মেনু বন্ধ, Escape-বন্ধ।

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

const setThemeMock = vi.fn();
const themeRef = { current: 'dark' as string };

vi.mock('../../contexts/useTheme', () => ({
  useTheme: () => ({ theme: themeRef.current, toggleTheme: vi.fn(), setTheme: setThemeMock }),
}));

import { ThemePicker } from './ThemePicker';

describe('ThemePicker (#4138 Phase 1 follow-up)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    themeRef.current = 'dark';
  });

  it('renders a trigger with menu semantics and the current theme label', () => {
    render(<ThemePicker />);
    const trigger = screen.getByRole('button', { name: /Theme: Deep Space/i });
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('opens a menu listing all 8 themes from THEME_META (SSOT labels)', () => {
    render(<ThemePicker />);
    fireEvent.click(screen.getByRole('button', { name: /Theme: Deep Space/i }));

    const menu = screen.getByRole('menu');
    expect(menu).toBeInTheDocument();

    // বাংলা: SSOT চুক্তি — THEME_META.label-ই মেনুর লেবেল; ৮টির একটিও কম নয়।
    const expectedLabels = [
      'Deep Space', 'Daylight', 'Synthwave', 'Cyberpunk',
      'Minimal', 'Sunset Ember', 'Matrix Rain', 'Emerald Deep',
    ];
    for (const label of expectedLabels) {
      expect(screen.getByRole('menuitemradio', { name: label })).toBeInTheDocument();
    }
    expect(screen.getAllByRole('menuitemradio')).toHaveLength(8);
  });

  it('marks the active theme with aria-checked=true', () => {
    themeRef.current = 'sunset';
    render(<ThemePicker />);
    fireEvent.click(screen.getByRole('button', { name: /Theme: Sunset Ember/i }));

    expect(screen.getByRole('menuitemradio', { name: 'Sunset Ember' })).toHaveAttribute(
      'aria-checked',
      'true'
    );
    expect(screen.getByRole('menuitemradio', { name: 'Deep Space' })).toHaveAttribute(
      'aria-checked',
      'false'
    );
  });

  it('calls setTheme with the chosen theme and closes the menu', () => {
    render(<ThemePicker />);
    const trigger = screen.getByRole('button', { name: /Theme: Deep Space/i });
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Cyberpunk' }));

    expect(setThemeMock).toHaveBeenCalledTimes(1);
    expect(setThemeMock).toHaveBeenCalledWith('cyberpunk');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('closes the menu on Escape key', () => {
    render(<ThemePicker />);
    fireEvent.click(screen.getByRole('button', { name: /Theme: Deep Space/i }));
    expect(screen.getByRole('menu')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('closes the menu on outside mousedown', () => {
    render(
      <div>
        <div data-testid="outside">outside</div>
        <ThemePicker />
      </div>
    );
    fireEvent.click(screen.getByRole('button', { name: /Theme: Deep Space/i }));
    expect(screen.getByRole('menu')).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByTestId('outside'));
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
