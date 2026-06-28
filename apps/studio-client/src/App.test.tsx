import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { App } from './App';

// Mock ResizeObserver for ReactFlow in JSDOM
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
global.ResizeObserver = MockResizeObserver as any;

// Mock the EvolutionForgeWidget subcomponent to simplify App tests
vi.mock('./App', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./App')>();
  return {
    ...actual,
    EvolutionForgeWidget: () => <div data-testid="evolution-forge">// AI Evolution Forge Mock</div>,
  };
});

const mockFetchGateStatus = vi.fn();
const mockExecuteGateOverride = vi.fn();
const mockSetServerStatus = vi.fn();
const mockForgeNewSkill = vi.fn();

const storeState = {
  isServerOnline: true,
  setServerStatus: mockSetServerStatus,
  streamLogs: ['log 1', 'log 2'],
  deployGate: {
    status: 'UNLOCKED',
    reason: 'Initial deploy clean',
  },
  fetchGateStatus: mockFetchGateStatus,
  executeGateOverride: mockExecuteGateOverride,
  isForging: false,
  forgeFeedback: null,
  forgeSuccessCode: null,
  forgeNewSkill: mockForgeNewSkill,
};

vi.mock('./store/useStore', () => ({
  useStore: () => storeState,
}));

// Mock EventSource globally
class MockEventSource {
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();
  constructor(url: string) {
    this.url = url;
    if (this.onopen) {
      this.onopen();
    }
  }
}

global.EventSource = MockEventSource as any;

describe('App component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storeState.isServerOnline = true;
    storeState.deployGate.status = 'UNLOCKED';
    storeState.deployGate.reason = 'Initial deploy clean';
  });

  it('renders header, title, and health status', () => {
    render(<App />);

    expect(screen.getByText('AETHEL WORKSPACE HUD | USER-01')).toBeInTheDocument();
    expect(screen.getByText('AETHEL CENTRAL WORKSPACE')).toBeInTheDocument();
    expect(screen.getByText(/📶 CORE:\s*ONLINE/i)).toBeInTheDocument();
  });

  it('renders chat console and voice interface status', () => {
    render(<App />);

    expect(screen.getByText('AETHEL | CHAT CONSOLE')).toBeInTheDocument();
    expect(screen.getByText('VOICE INTERFACE')).toBeInTheDocument();
    expect(screen.getByText('🎤 Speaking... Waveform active')).toBeInTheDocument();
  });

  it('allows user to send messages in the chat console', async () => {
    render(<App />);

    const input = screen.getByPlaceholderText('[Type message...]');
    fireEvent.change(input, { target: { value: 'Test message' } });

    // The send button contains the Send Lucide icon
    const sendButton = screen.getByRole('button');
    fireEvent.click(sendButton);

    expect(screen.getByText('Test message')).toBeInTheDocument();
    expect(screen.getByText('Analyzing request "Test message"... Processing on central core.')).toBeInTheDocument();
  });
});
