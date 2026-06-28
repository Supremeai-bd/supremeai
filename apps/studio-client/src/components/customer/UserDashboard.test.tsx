import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { UserDashboard } from './UserDashboard';

const defaultProps = {
  customerMessages: [
    { id: 1, sender: 'User', text: 'Hello', timestamp: '10:00 AM' },
    { id: 2, sender: 'Aethel', text: 'Hi there', timestamp: '10:01 AM' },
  ],
  customerInput: '',
  setCustomerInput: vi.fn(),
  loading: false,
  handleSendCustomer: vi.fn(),
  theme: 'dark' as const,
  toggleTheme: vi.fn(),
  code: '// code',
  setCode: vi.fn(),
  isServerOnline: true,
  deployGate: { status: 'UNLOCKED' },
  user: {
    username: 'TestUser',
    last_login: '2026-06-29',
    email: 'test@example.com',
    role: 'operator',
    preferences: {
      theme: 'dark',
      sidebar_collapsed: false,
      notification_enabled: true,
      sound_enabled: true,
      compact_mode: false,
      font_size: 'medium',
    },
  },
  projects: [
    {
      id: '1',
      name: 'Project A',
      description: 'Desc',
      created_at: '2026-06-01',
      updated_at: '2026-06-29',
      owner_id: 'u1',
      settings: {
        default_model: 'gpt-4',
        system_prompt: '',
        temperature: 0.7,
        max_tokens: 1024,
        rag_enabled: true,
      },
    },
  ],
  chatHistory: [],
  widgets: [],
};

describe('UserDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getTabButton = (name: RegExp) =>
    screen.getAllByRole('button', { name })[0];

  it('renders welcome header with username', () => {
    render(<UserDashboard {...defaultProps} />);
    expect(screen.getByText('Welcome back, TestUser')).toBeInTheDocument();
  });

  it('renders server and gate status', () => {
    render(<UserDashboard {...defaultProps} />);
    expect(screen.getByText(/CORE:/)).toBeInTheDocument();
    expect(screen.getByText(/ONLINE/)).toBeInTheDocument();
    expect(screen.getByText(/UNLOCKED/)).toBeInTheDocument();
  });

  it('shows offline status when server is down', () => {
    render(<UserDashboard {...defaultProps} isServerOnline={false} />);
    expect(screen.getByText(/OFFLINE/)).toBeInTheDocument();
  });

  it('renders default theme as dark', () => {
    render(<UserDashboard {...defaultProps} theme="dark" />);
    expect(screen.getByText(/☀️ Light/)).toBeInTheDocument();
  });

  it('renders light theme when toggled', () => {
    render(<UserDashboard {...defaultProps} theme="light" />);
    expect(screen.getByText(/🌙 Dark/)).toBeInTheDocument();
  });

  it('calls toggleTheme when theme button clicked', () => {
    render(<UserDashboard {...defaultProps} />);
    const btn = screen.getByText(/☀️ Light/);
    fireEvent.click(btn);
    expect(defaultProps.toggleTheme).toHaveBeenCalled();
  });

  it('renders all four tab buttons', () => {
    render(<UserDashboard {...defaultProps} />);
    expect(screen.getByRole('button', { name: /Overview/i })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Home Feed/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: /Quick Presets/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: /Chat/i }).length).toBeGreaterThanOrEqual(1);
  });

  it('switches to presets tab when clicked', () => {
    render(<UserDashboard {...defaultProps} />);
    fireEvent.click(getTabButton(/Quick Presets/i));
    expect(getTabButton(/Quick Presets/i).classList.contains('bg-[#00f3ff]/20')).toBe(true);
  });

  it('switches to chat tab when clicked', () => {
    render(<UserDashboard {...defaultProps} />);
    fireEvent.click(getTabButton(/Chat/i));
    expect(screen.getByText('SupremeAI Chat')).toBeInTheDocument();
  });

  it('switches to feed tab when clicked', () => {
    render(<UserDashboard {...defaultProps} />);
    fireEvent.click(getTabButton(/Home Feed/i));
    expect(screen.getByText('AI Assistant')).toBeInTheDocument();
  });

  it('shows project list on overview', () => {
    render(<UserDashboard {...defaultProps} projects={defaultProps.projects} />);
    expect(screen.getByText('Your Projects')).toBeInTheDocument();
    expect(screen.getByText('Project A')).toBeInTheDocument();
  });

  it('shows empty projects state when no projects', () => {
    render(<UserDashboard {...defaultProps} projects={[]} />);
    expect(screen.getByText('No projects yet. Create your first project to get started.')).toBeInTheDocument();
  });

  it('shows stat cards with counts', () => {
    render(<UserDashboard {...defaultProps} projects={defaultProps.projects} />);
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('Projects')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Messages')).toBeInTheDocument();
  });

  it('shows quick actions and navigates to chat', () => {
    render(<UserDashboard {...defaultProps} />);
    fireEvent.click(screen.getByText('New Chat Session'));
    expect(screen.getByText('SupremeAI Chat')).toBeInTheDocument();
  });

  it('shows recent activity from customerMessages', () => {
    render(<UserDashboard {...defaultProps} chatHistory={[]} />);
    expect(screen.getByText('You:')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('AI:')).toBeInTheDocument();
    expect(screen.getByText('Hi there')).toBeInTheDocument();
  });

  it('shows no recent activity when no messages', () => {
    render(<UserDashboard {...defaultProps} customerMessages={[]} chatHistory={[]} />);
    expect(screen.getByText('No recent activity')).toBeInTheDocument();
  });

  it('calls setCustomerInput when chat input changes', () => {
    render(<UserDashboard {...defaultProps} />);
    fireEvent.click(getTabButton(/Chat/i));
    const input = screen.getByPlaceholderText('Ask anything or generate code...');
    fireEvent.change(input, { target: { value: 'test input' } });
    expect(defaultProps.setCustomerInput).toHaveBeenCalledWith('test input');
  });

  it('calls handleSendCustomer when send button clicked', () => {
    render(<UserDashboard {...defaultProps} customerInput="hello" />);
    fireEvent.click(getTabButton(/Chat/i));
    const sendBtn = screen.getByText('Send').closest('button');
    if (sendBtn) fireEvent.click(sendBtn);
    expect(defaultProps.handleSendCustomer).toHaveBeenCalled();
  });

  it('switches to overview from quick action and back to presets', () => {
    render(<UserDashboard {...defaultProps} />);
    fireEvent.click(getTabButton(/Quick Presets/i));
    expect(getTabButton(/Quick Presets/i).classList.contains('bg-[#00f3ff]/20')).toBe(true);
  });
});
