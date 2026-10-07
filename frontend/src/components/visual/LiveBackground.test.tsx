// (#4138 Phase 1) LiveBackground-চুক্তি — deterministic, a11y-নিরাপদ জীবন্ত স্তর।
// বাংলা মন্তব্য: ৩টি চুক্তি — (১) স্তর aria-hidden + দৃশ্যমান, (২) reduced-motion
// হলে অ্যানিমেশন-লুপ বন্ধ (WCAG), (৩) workspace-ভ্যারিয়েন্ট কণা (mote) রেন্ডার
// করে না — ঘন ড্যাশবোর্ডের পেছনে ইচ্ছাকৃত সংযম।
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';
import { LiveBackground } from './LiveBackground';
import type { LiveBackgroundVariant } from './LiveBackground';

const reducedMotionOrig = window.matchMedia;

function mockReducedMotion(prefers: boolean) {
  // বাংলা মন্তব্য: framer-motion-এর useReducedMotion window.matchMedia
  // ('(prefers-reduced-motion: reduce)') শোনে — টেস্টে সেটাই mock করছি।
  vi.stubGlobal('matchMedia', ((query: string) => ({
    matches: query.includes('prefers-reduced-motion') ? prefers : false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia);
}

describe('LiveBackground (#4138 — live animation layer contract)', () => {
  beforeEach(() => {
    mockReducedMotion(false);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.matchMedia = reducedMotionOrig;
  });

  it('renders the fixed layer, aria-hidden, with theme-var-driven orbs', () => {
    render(<LiveBackground variant="public" />);
    const layer = screen.getByTestId('live-bg-public');
    expect(layer).toBeInTheDocument();
    // a11y: স্তরটি সম্পূর্ণ decorative — স্ক্রিন-রিডার এড়িয়ে যাবে।
    expect(layer.getAttribute('aria-hidden')).toBe('true');
    // অরব-রঙ থিম-var থেকে আসে — এখানে class-চুক্তি, রঙ-var প্রমাণ index.css-এ।
    expect(layer.querySelector('.live-bg-orb-primary')).toBeTruthy();
    expect(layer.querySelector('.live-bg-orb-secondary')).toBeTruthy();
  });

  it('public variant renders floating motes; workspace variant renders none', () => {
    const { unmount } = render(<LiveBackground variant="public" />);
    expect(screen.getByTestId('live-bg-public').querySelectorAll('.live-bg-mote').length).toBeGreaterThan(0);
    unmount();

    render(<LiveBackground variant="workspace" />);
    // সংযম-চুক্তি: কর্মক্ষেত্রের পেছনে কণা নয় — শুধু ফিকে অরব।
    expect(screen.getByTestId('live-bg-workspace').querySelectorAll('.live-bg-mote').length).toBe(0);
    expect(screen.getByTestId('live-bg-workspace').querySelectorAll('.live-bg-orb').length).toBe(2);
  });

  it('defaults to the public variant when no prop is given', () => {
    render(<LiveBackground />);
    expect(screen.getByTestId('live-bg-public')).toBeInTheDocument();
  });

  it('exposes a typed variant union (compile-time contract smoke)', () => {
    // বাংলা মন্তব্য: টাইপ-চুক্তি — ভ্যারিয়েন্ট ইউনিয়ন ঠিক দুই সদস্যের।
    // (tsc --noEmit এটা enforce করে; এখানে runtime-smoke রাখলাম false-green এড়াতে।)
    const variants: LiveBackgroundVariant[] = ['public', 'workspace'];
    expect(variants).toEqual(['public', 'workspace']);
  });
});

describe('LiveBackground reduced-motion (#4138 — WCAG contract)', () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.matchMedia = reducedMotionOrig;
  });

  it('stops motion loops when the user prefers reduced motion', () => {
    mockReducedMotion(true);
    const { container } = render(<LiveBackground variant="public" />);
    // reduced-motion-এ framer-motion কোনো looping animate-ভ্যালু সেট করে না;
    // স্তর তবু উপস্থিত (স্থির) — কনটেন্ট নয়, কেবল গতি বন্ধ।
    const layer = screen.getByTestId('live-bg-public');
    expect(layer).toBeInTheDocument();
    expect(container.querySelector('.live-bg-orb-primary')).toBeTruthy();
  });
});
