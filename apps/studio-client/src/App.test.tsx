import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from './App';

global.fetch = vi.fn();

beforeEach(() => {
  vi.resetAllMocks();
});

describe('App component', () => {
  it('renders titlebar and initial AI message', () => {
    render(<App />);

    expect(screen.getByText('SUPREME')).toBeInTheDocument();
    expect(screen.getByText(/স্বাগতম! আমি SupremeAI মাস্টার অ্যাসিস্ট্যান্ট/i)).toBeInTheDocument();
  });

  it('renders editor area placeholder', () => {
    render(<App />);

    expect(screen.getByText('main.js')).toBeInTheDocument();
  });

  it('shows default AI greeting message on initial load', () => {
    render(<App />);

    expect(
      screen.getByText(/স্বাগতম! আমি SupremeAI মাস্টার অ্যাসিস্ট্যান্ট/i)
    ).toBeInTheDocument();
  });

  it('allows typing in the chat input', () => {
    render(<App />);

    const input = screen.getByPlaceholderText('Ask anything or generate code...');
    fireEvent.change(input, { target: { value: 'review this code' } });

    expect(input).toHaveValue('review this code');
  });

  it('sends a message to the backend when input is non-empty and Enter is pressed', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ result: 'Here is a suggestion' }),
    });

    render(<App />);

    const input = screen.getByPlaceholderText('Ask anything or generate code...');
    fireEvent.change(input, { target: { value: 'review this code' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText('review this code')).toBeInTheDocument();
    });
  });

  it('shows user message immediately and AI response after fetch', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ result: 'Suggested fix...' }),
    });

    render(<App />);

    const input = screen.getByPlaceholderText('Ask anything or generate code...');
    fireEvent.change(input, { target: { value: 'fix this bug' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(screen.getByText('fix this bug')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Suggested fix...')).toBeInTheDocument();
    });
  });

  it('does not send empty messages', () => {
    render(<App />);

    const input = screen.getByPlaceholderText('Ask anything or generate code...');
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    const userMessages = screen.queryAllByText(/fix this bug|review this code/);
    expect(userMessages.length).toBe(0);
  });

  it('renders status bar with agent server status text', () => {
    render(<App />);

    expect(screen.getByText(/Agent Server Status: Online/i)).toBeInTheDocument();
  });

  it('renders nav sidebar buttons', () => {
    render(<App />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });
});
