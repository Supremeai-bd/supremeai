import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QuickPresets } from './QuickPresets';

describe('QuickPresets', () => {
  it('renders the Quick Presets header', () => {
    render(<QuickPresets onSelectPreset={vi.fn()} />);
    expect(screen.getByText('Quick Presets')).toBeInTheDocument();
  });

  it('renders all preset cards', () => {
    render(<QuickPresets onSelectPreset={vi.fn()} />);
    expect(screen.getByText('Code Generator')).toBeInTheDocument();
    expect(screen.getByText('Translator')).toBeInTheDocument();
    expect(screen.getByText('Content Writer')).toBeInTheDocument();
  });

  it('renders preset descriptions', () => {
    render(<QuickPresets onSelectPreset={vi.fn()} />);
    expect(screen.getByText('Python binary search algorithm')).toBeInTheDocument();
    expect(screen.getByText('Translate to Bengali')).toBeInTheDocument();
    expect(screen.getByText('Startup marketing email')).toBeInTheDocument();
  });

  it('calls onSelectPreset with the correct prompt when a preset is clicked', () => {
    const onSelectPreset = vi.fn();
    render(<QuickPresets onSelectPreset={onSelectPreset} />);

    fireEvent.click(screen.getByText('Code Generator'));
    expect(onSelectPreset).toHaveBeenCalledWith('Python binary search algorithm design');
  });

  it('calls onSelectPreset for the Translator preset', () => {
    const onSelectPreset = vi.fn();
    render(<QuickPresets onSelectPreset={onSelectPreset} />);

    fireEvent.click(screen.getByText('Translator'));
    expect(onSelectPreset).toHaveBeenCalledWith("Translate 'Welcome to SupremeAI' to Bengali");
  });

  it('calls onSelectPreset for the Content Writer preset', () => {
    const onSelectPreset = vi.fn();
    render(<QuickPresets onSelectPreset={onSelectPreset} />);

    fireEvent.click(screen.getByText('Content Writer'));
    expect(onSelectPreset).toHaveBeenCalledWith('Write a marketing email for an AI startup');
  });

  it('renders the Operator Core Ready status', () => {
    render(<QuickPresets onSelectPreset={vi.fn()} />);
    expect(screen.getByText('Operator Core Ready')).toBeInTheDocument();
  });
});
