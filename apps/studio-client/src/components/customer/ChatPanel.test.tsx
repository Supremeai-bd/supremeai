import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatPanel } from './ChatPanel';
import type { ChatMessage } from '../../types';

const baseMessages: ChatMessage[] = [
  { id: '1', sender: 'user', text: 'Hello AI', timestamp: '10:00 AM' },
  { id: '2', sender: 'ai', text: 'Hi user!', timestamp: '10:01 AM' },
];

describe('ChatPanel', () => {
  it('renders the SupremeAI Chat header', () => {
    render(
      <ChatPanel
        messages={baseMessages}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        loading={false}
      />,
    );
    expect(screen.getByText('SupremeAI Chat')).toBeInTheDocument();
  });

  it('renders the ONLINE status badge', () => {
    render(
      <ChatPanel
        messages={baseMessages}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        loading={false}
      />,
    );
    expect(screen.getByText('ONLINE')).toBeInTheDocument();
  });

  it('renders user and AI messages', () => {
    render(
      <ChatPanel
        messages={baseMessages}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        loading={false}
      />,
    );
    expect(screen.getByText('Hello AI')).toBeInTheDocument();
    expect(screen.getByText('Hi user!')).toBeInTheDocument();
  });

  it('calls onInputChange when typing in the input', () => {
    const onInputChange = vi.fn();
    render(
      <ChatPanel
        messages={baseMessages}
        input=""
        onInputChange={onInputChange}
        onSend={vi.fn()}
        loading={false}
      />,
    );
    const input = screen.getByPlaceholderText('Ask anything or generate code...');
    fireEvent.change(input, { target: { value: 'test' } });
    expect(onInputChange).toHaveBeenCalledWith('test');
  });

  it('calls onSend when clicking the Send button', () => {
    const onSend = vi.fn();
    render(
      <ChatPanel
        messages={baseMessages}
        input="hello"
        onInputChange={vi.fn()}
        onSend={onSend}
        loading={false}
      />,
    );
    fireEvent.click(screen.getByText('Send'));
    expect(onSend).toHaveBeenCalled();
  });

  it('calls onSend when pressing Enter in the input', () => {
    const onSend = vi.fn();
    render(
      <ChatPanel
        messages={baseMessages}
        input="hello"
        onInputChange={vi.fn()}
        onSend={onSend}
        loading={false}
      />,
    );
    const input = screen.getByPlaceholderText('Ask anything or generate code...');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSend).toHaveBeenCalled();
  });

  it('renders the thinking indicator when loading', () => {
    render(
      <ChatPanel
        messages={baseMessages}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        loading={true}
      />,
    );
    expect(screen.getByText('SupremeAI is thinking...')).toBeInTheDocument();
  });

  it('renders timestamps for messages', () => {
    render(
      <ChatPanel
        messages={baseMessages}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        loading={false}
      />,
    );
    expect(screen.getByText('10:00 AM')).toBeInTheDocument();
    expect(screen.getByText('10:01 AM')).toBeInTheDocument();
  });

  it('calls onSend when pressing Enter in the input even if empty', () => {
    const onSend = vi.fn();
    render(
      <ChatPanel
        messages={[]}
        input=""
        onInputChange={vi.fn()}
        onSend={onSend}
        loading={false}
      />,
    );
    const input = screen.getByPlaceholderText('Ask anything or generate code...');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSend).toHaveBeenCalled();
  });

  it('shows an empty messages container when there are no messages', () => {
    const { container } = render(
      <ChatPanel
        messages={[]}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        loading={false}
      />,
    );
    const messagesArea = container.querySelector('.overflow-y-auto');
    expect(messagesArea).toBeInTheDocument();
  });
});
