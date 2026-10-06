/**
 * #3269: CommandCenterApp — Vitest coverage (rendering + composition contract).
 *
 * বাংলা: shell component-এর আসল চুক্তি — ৫টি অংশ (CommandBar, CommandPalette,
 * LeftRail, WorkspaceViewport, BottomDeck) রেন্ডার হয়, data hooks থেকে
 * health/metrics প্রপে প্রবাহিত হয়।
 * ESM import (require() নয়), child modules + data hooks mocked।
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const { useMetricsMock, useHealthMapMock } = vi.hoisted(() => ({
  useMetricsMock: vi.fn(),
  useHealthMapMock: vi.fn(),
}));

vi.mock('../data/hooks', () => ({
  useMetrics: useMetricsMock,
  useHealthMap: useHealthMapMock,
}));

vi.mock('../shell/CommandBar', () => ({
  CommandBar: ({ healthPercent }: { healthPercent: number | null }) => (
    <div data-testid="command-bar" data-health={healthPercent ?? 'none'} />
  ),
}));
vi.mock('../shell/CommandPalette', () => ({
  CommandPalette: () => <div data-testid="command-palette" />,
}));
vi.mock('../shell/LeftRail', () => ({
  LeftRail: () => <nav data-testid="left-rail" />,
}));
vi.mock('../shell/WorkspaceViewport', () => ({
  WorkspaceViewport: () => <main data-testid="workspace-viewport" />,
}));
vi.mock('../shell/BottomDeck', () => ({
  BottomDeck: ({ metrics }: { metrics: unknown }) => (
    <div data-testid="bottom-deck" data-has-metrics={String(metrics !== null)} />
  ),
}));

import { CommandCenterApp } from '../shell/CommandCenterApp';

const baseMetrics = { agents_online: 3 } as never;
const baseHealth = { overall_health_percent: 87 } as never;

describe('CommandCenterApp — composition contract', () => {
  it('renders all five shell sections', () => {
    useMetricsMock.mockReturnValue({ data: baseMetrics });
    useHealthMapMock.mockReturnValue({ data: baseHealth });
    render(<CommandCenterApp />);
    for (const id of [
      'command-bar',
      'command-palette',
      'left-rail',
      'workspace-viewport',
      'bottom-deck',
    ]) {
      expect(screen.getByTestId(id)).toBeTruthy();
    }
  });

  it('flows health percent from useHealthMap into CommandBar', () => {
    useMetricsMock.mockReturnValue({ data: null });
    useHealthMapMock.mockReturnValue({ data: { overall_health_percent: 42 } as never });
    render(<CommandCenterApp />);
    expect(screen.getByTestId('command-bar').getAttribute('data-health')).toBe('42');
  });

  it('health null → CommandBar gets null (not crash)', () => {
    useMetricsMock.mockReturnValue({ data: null });
    useHealthMapMock.mockReturnValue({ data: undefined });
    render(<CommandCenterApp />);
    expect(screen.getByTestId('command-bar').getAttribute('data-health')).toBe('none');
  });

  it('flows metrics from useMetrics into BottomDeck', () => {
    useMetricsMock.mockReturnValue({ data: baseMetrics });
    useHealthMapMock.mockReturnValue({ data: null });
    render(<CommandCenterApp />);
    expect(screen.getByTestId('bottom-deck').getAttribute('data-has-metrics')).toBe('true');
  });

  it('metrics null → BottomDeck has-metrics false (graceful empty state)', () => {
    useMetricsMock.mockReturnValue({ data: null });
    useHealthMapMock.mockReturnValue({ data: null });
    render(<CommandCenterApp />);
    expect(screen.getByTestId('bottom-deck').getAttribute('data-has-metrics')).toBe('false');
  });

  it('subscribes metrics with 15s poll and health with 45s poll', () => {
    useMetricsMock.mockReturnValue({ data: null });
    useHealthMapMock.mockReturnValue({ data: null });
    render(<CommandCenterApp />);
    expect(useMetricsMock).toHaveBeenCalledWith(15_000);
    expect(useHealthMapMock).toHaveBeenCalledWith(45_000);
  });
});
