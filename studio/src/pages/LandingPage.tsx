import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ConceptApp } from './concept/ConceptApp';
import { DreamBuilderHero } from '../components/landing/DreamBuilderHero';
import { NeuralConstellationCanvas } from '../components/common/NeuralConstellationCanvas';

// ROOT-CAUSE FIX (Refs #876 / bridge-20261023-frontend-router-restore):
// CTAs previously targeted /signup (a route that does not exist) and
// /workspace/live (now a protected AIStudio route). Canonical split-auth
// route is /register; the public guest chat lives at /chat.
export const LandingHeader: React.FC = () => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const onLanding = pathname === '/';
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);
  const navTo = (path: string) => {
    setMenuOpen(false);
    navigate(path);
  };
  return (
    <header className="sticky top-0 z-overlay flex h-16 w-full items-center justify-between border-b border-white/10 bg-slate-950/70 px-4 sm:px-6 backdrop-blur-xl">
      <Link
        to="/"
        className="flex items-center gap-3 py-3 -my-3"
        aria-label="SupremeAI home"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-400 via-indigo-500 to-purple-600 font-bold text-white shadow-lg shadow-purple-500/20">
          S
        </span>
        <span className="text-lg font-bold tracking-tight text-white">SupremeAI</span>
      </Link>

      <nav className="hidden md:flex items-center gap-6 text-sm text-slate-300">
        <Link to="/features" className="hover:text-cyan-300 transition-colors">
          Features
        </Link>
        <Link to="/models" className="hover:text-cyan-300 transition-colors">
          Models
        </Link>
        <Link to="/pricing" className="hover:text-cyan-300 transition-colors">
          Pricing
        </Link>
        <Link to="/docs" className="hover:text-cyan-300 transition-colors">
          Docs
        </Link>
        <Link to="/chat" className="flex items-center gap-1.5 text-cyan-300 hover:text-cyan-200 transition-colors font-medium">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
          <span>Live Chat</span>
        </Link>
      </nav>

      <div className="flex items-center gap-3">
        {/* Mobile hamburger: nav links were hidden md:flex with no mobile fallback.
            #1696 D3: p-3 keeps the 20px icon but lifts the tap target from 36px
            to the 44px platform ergonomics minimum (WCAG 2.5.8 passes at 24px,
            mobile ergonomics guidance wants 44px+). */}
        <button
          type="button"
          aria-label="Toggle navigation menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)}
          className="md:hidden rounded-lg p-3 -m-1 text-slate-300 hover:text-white hover:bg-white/5 transition-colors"
        >
          {menuOpen ? (
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          ) : (
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
          )}
        </button>
        <button
          type="button"
          onClick={() => navigate('/login')}
          className="hidden sm:block rounded-lg px-3.5 py-1.5 text-sm font-medium text-slate-300 hover:text-white transition-colors"
        >
          Sign In
        </button>
        <button
          type="button"
          onClick={() => navigate('/register')}
          className="hidden sm:block rounded-lg bg-gradient-to-r from-emerald-500 to-purple-600 px-4 py-1.5 text-sm font-semibold text-white shadow-md shadow-emerald-500/20 hover:opacity-95 transition-opacity"
        >
          Get Started
        </button>
      </div>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <nav className="absolute top-16 left-0 right-0 z-modal flex flex-col gap-1 border-b border-white/10 bg-slate-950/95 px-4 py-4 backdrop-blur-xl md:hidden">
          <Link to="/features" onClick={closeMenu} className="rounded-lg px-3 py-2.5 text-sm text-slate-300 hover:text-cyan-300 hover:bg-white/5 transition-colors">
            Features
          </Link>
          <Link to="/models" onClick={closeMenu} className="rounded-lg px-3 py-2.5 text-sm text-slate-300 hover:text-cyan-300 hover:bg-white/5 transition-colors">
            Models
          </Link>
          <Link to="/pricing" onClick={closeMenu} className="rounded-lg px-3 py-2.5 text-sm text-slate-300 hover:text-cyan-300 hover:bg-white/5 transition-colors">
            Pricing
          </Link>
          <Link to="/docs" onClick={closeMenu} className="rounded-lg px-3 py-2.5 text-sm text-slate-300 hover:text-cyan-300 hover:bg-white/5 transition-colors">
            Docs
          </Link>
          <Link to="/chat" onClick={closeMenu} className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-cyan-300 hover:bg-white/5 transition-colors font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
            <span>Live Chat</span>
          </Link>
          <div className="mt-2 flex flex-col gap-2 border-t border-white/10 pt-3">
            <button type="button" onClick={() => navTo('/login')} className="rounded-lg border border-white/10 px-3 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/5 transition-colors">Sign In</button>
            <button type="button" onClick={() => navTo('/register')} className="rounded-lg bg-gradient-to-r from-cyan-500 to-indigo-600 px-3 py-2.5 text-sm font-semibold text-white shadow-md shadow-cyan-500/20 hover:opacity-95 transition-opacity">Get Started</button>
          </div>
        </nav>
      )}
    </header>
  );
};

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!location.hash) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const scroll = () => {
      const el = document.querySelector(location.hash);
      if (el) el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
    };
    const t = window.setTimeout(scroll, 50);
    return () => window.clearTimeout(t);
  }, [location.hash]);

  return (
    <div className="relative min-h-screen w-full bg-[#080b12] text-slate-100 overflow-x-hidden">
      <NeuralConstellationCanvas />
      <LandingHeader />

      {/* Living Dream Builder Interactive Hero */}
      <div className="relative z-10 pb-8">
        <DreamBuilderHero />
      </div>

      {/* Quick Entry Callout to Live Chat */}
      <section className="relative z-10 border-t border-white/10 px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-4xl rounded-3xl border border-white/10 bg-slate-900/60 p-8 backdrop-blur-xl text-center">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">
            Ready to experience sovereign intelligence?
          </h2>
          <p className="mt-3 text-slate-400 max-w-xl mx-auto">
            Try our instant live assistant with zero setup. Ask questions, explore code, or build workflows directly in your browser.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-4">
            <button
              type="button"
              onClick={() => navigate('/chat')}
              className="rounded-xl bg-gradient-to-r from-emerald-500 via-cyan-500 to-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-500/25 hover:opacity-95 transition-opacity"
            >
              Start Free Guest Chat →
            </button>
            <button
              type="button"
              onClick={() => navigate('/features')}
              className="rounded-xl border border-white/15 bg-white/5 px-6 py-3 text-sm font-medium text-slate-200 hover:bg-white/10 transition-colors"
            >
              Explore All Features
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
