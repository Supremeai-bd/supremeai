import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { App } from './App';

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
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 0);
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

    expect(screen.getByText('SupremeAI Studio Console 2.0')).toBeInTheDocument();
    expect(screen.getByText('Autonomic & Hardened Production Core')).toBeInTheDocument();
    expect(screen.getByText('CORE: ONLINE')).toBeInTheDocument();
  });

  it('renders telemetry and streaming sections', () => {
    render(<App />);

    expect(screen.getByText('// Deploy Gate Telemetry')).toBeInTheDocument();
    expect(screen.getByText('// Active Infrastructure Streaming Stack')).toBeInTheDocument();
    expect(screen.getByText('→ log 1')).toBeInTheDocument();
    expect(screen.getByText('→ log 2')).toBeInTheDocument();
  });

  it('shows override panel when clicking the trigger override button', async () => {
    render(<App />);

    const button = screen.getByText('🔱 Trigger God-Mode Gate Override');
    fireEvent.click(button);

    expect(screen.getByText('🔱 God-Mode Override Override')).toBeInTheDocument();
    expect(screen.getByLabelText('Architect Justification')).toBeInTheDocument();
    expect(screen.getByLabelText('Master Secret Vault Token')).toBeInTheDocument();
  });

  it('submits override form successfully', async () => {
    mockExecuteGateOverride.mockResolvedValueOnce({ success: true, message: 'Gate unlocked successfully' });
    render(<App />);

    const triggerBtn = screen.getByText('🔱 Trigger God-Mode Gate Override');
    fireEvent.click(triggerBtn);

    const justificationInput = screen.getByPlaceholderText('Minimum 10 characters required...');
    const secretInput = screen.getByPlaceholderText('Enter secret key...');
    const form = screen.getByRole('button', { name: /Execute Global Override Commit/i }).closest('form');

    fireEvent.change(justificationInput, { target: { value: 'Forced bypass for hotfix' } });
    fireEvent.change(secretInput, { target: { value: 'master-token-123' } });

    expect(form).toBeInTheDocument();
    fireEvent.submit(form!);

    expect(mockExecuteGateOverride).toHaveBeenCalledWith('UNLOCKED', 'Forced bypass for hotfix', 'master-token-123');
  });
});
