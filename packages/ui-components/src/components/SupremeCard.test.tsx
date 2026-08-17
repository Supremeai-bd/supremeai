import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SupremeCard } from './SupremeCard';

describe('SupremeCard', () => {
  it('renders children', () => {
    render(<SupremeCard>Hello World</SupremeCard>);
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('applies default classes', () => {
    render(<SupremeCard data-testid="card">Content</SupremeCard>);
    const el = screen.getByTestId('card');
    expect(el.className).toContain('rounded-3xl');
    expect(el.className).toContain('border');
    expect(el.className).toContain('backdrop-blur-xl');
  });

  it('applies custom className', () => {
    render(<SupremeCard className="w-full h-64" data-testid="card">Content</SupremeCard>);
    const el = screen.getByTestId('card');
    expect(el.className).toContain('w-full');
    expect(el.className).toContain('h-64');
  });

  it('applies glow styles when enabled', () => {
    render(<SupremeCard glow data-testid="card">Content</SupremeCard>);
    const el = screen.getByTestId('card');
    expect(el.className).toContain('shadow-[');
  });

  it('removes blur when disabled', () => {
    render(<SupremeCard blur={false} data-testid="card">Content</SupremeCard>);
    const el = screen.getByTestId('card');
    expect(el.className).not.toContain('backdrop-blur-xl');
  });

  it('passes through additional props', () => {
    render(<SupremeCard data-testid="card" aria-label="test-card">Content</SupremeCard>);
    const el = screen.getByTestId('card');
    expect(el.getAttribute('aria-label')).toBe('test-card');
  });
});
