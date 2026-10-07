import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUp, BrainCircuit, Check, ChevronDown, Clock, Database, Download, FileCode2, FileText, GitBranch, History, Image as ImageIcon, LayoutTemplate, Menu, Paperclip, Plus, Search, Share2, Sparkles, Telescope, Terminal, WandSparkles, Wrench, X, Zap } from 'lucide-react';
import { LiveBackground } from '../components/visual/LiveBackground';

const publicLinks = [
  { to: '/', label: 'Chat' },
  { to: '/models', label: 'Models' },
  { to: '/features', label: 'Features' },
  { to: '/pricing', label: 'Pricing' },
  { to: '/docs', label: 'Docs' },
  { to: '/about', label: 'About' },
];

const capabilityItems = [
  { title: 'History', text: 'Save and revisit conversations', icon: History, href: '/login' },
  { title: 'Files', text: 'Bring your own context', icon: FileText, href: '/login' },
  { title: 'Tools', text: 'Connect actions and workflows', icon: Wrench, href: '/login' },
  { title: 'Runs', text: 'Turn ideas into repeatable work', icon: Zap, href: '/login' },
  { title: 'Workspace', text: 'Keep projects and context together', icon: Sparkles, href: '/login' },
];

function CapabilityStrip({ onProtected }: { onProtected: (feature: string) => void }) {
  // Issue #1460: protected capability chips used to navigate straight to
  // /login (or /register), destroying the guest's in-progress chat. They now
  // raise an in-page auth prompt instead — no navigation, state intact.
  return <nav className="relative z-10 mx-auto flex w-full max-w-7xl gap-2 overflow-x-auto px-4 pt-24 sm:px-8" aria-label="SupremeAI capabilities">
    <Link to="/" className="shrink-0 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-2 text-xs font-medium text-cyan-200">Chat</Link>
    {capabilityItems.map(({ title, icon: Icon }) => <button key={title} type="button" onClick={() => onProtected(title)} className="flex shrink-0 items-center gap-2 rounded-full border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-slate-500 transition hover:border-cyan-300/30 hover:text-slate-200"><Icon size={13} aria-hidden="true" />{title}</button>)}
  </nav>;
}

function AuthPromptModal({ feature, onClose }: { feature: string; onClose: () => void }) {
  // Issue #1460: "Sign in to access [Feature]" without navigating away.
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4" role="dialog" aria-modal="true" aria-label={`Sign in to access ${feature}`} onClick={onClose}>
    <div className="w-full max-w-sm rounded-3xl border border-white/10 bg-[#171a20] p-7 shadow-2xl" onClick={(event) => event.stopPropagation()}>
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-lg font-medium text-slate-100">Sign in to access {feature.toLowerCase()}</h2>
        <button type="button" onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 text-slate-400 transition hover:bg-white/10 hover:text-slate-200"><X size={16} /></button>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-500">Your conversation stays right here — create an account or sign in when you are ready, and this page will keep your state.</p>
      <div className="mt-6 flex flex-col gap-2">
        <Link to="/login" className="rounded-full bg-cyan-300 px-4 py-2.5 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-200">Sign in</Link>
        <Link to="/register" className="rounded-full border border-white/15 px-4 py-2.5 text-center text-sm font-medium text-slate-200 transition hover:border-cyan-300/40">Create account</Link>
      </div>
    </div>
  </div>;
}

const intents = [
  { label: 'Research', prompt: 'Help me research a topic and organize the key findings.', icon: Search },
  { label: 'Write', prompt: 'Help me write a clear, useful first draft.', icon: WandSparkles },
  { label: 'Build', prompt: 'Help me turn an idea into a practical build plan.', icon: Zap },
  { label: 'Analyze', prompt: 'Help me analyze this problem and decide what to do next.', icon: Sparkles },
];

const models = [
  { name: 'Supreme Auto', detail: 'Best balance for everyday work', tag: 'Recommended' },
  { name: 'Reasoning Pro', detail: 'Deep analysis and complex planning', tag: 'Reasoning' },
  { name: 'Fast Chat', detail: 'Quick answers and brainstorming', tag: 'Fast' },
];

export function PublicHeader() {
  const [menuOpen, setMenuOpen] = React.useState(false);
  return <header className="absolute inset-x-0 top-0 z-20 border-b border-white/[0.06] px-4 py-4 sm:px-8 sm:py-5">
    <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
      <Link to="/" aria-label="SupremeAI home" className="flex shrink-0 items-center gap-3 text-sm font-semibold tracking-[0.18em] text-slate-100"><span className="flex size-8 items-center justify-center rounded-xl bg-cyan-300 font-mono text-sm font-bold text-slate-950 shadow-[0_0_24px_rgba(103,232,249,0.25)]">S</span><span className="hidden sm:inline">SUPREMEAI</span></Link>
      <nav className="hidden items-center gap-4 md:flex lg:gap-6" aria-label="Public navigation">{publicLinks.map((link) => <Link key={link.to} to={link.to} className="text-sm text-slate-500 transition hover:text-slate-100">{link.label}</Link>)}</nav>
      <div className="flex items-center gap-2 sm:gap-3"><span className="hidden items-center gap-2 text-xs text-slate-600 lg:flex"><span className="size-1.5 rounded-full bg-emerald-400" />Guest mode</span><Link to="/login" className="hidden text-sm text-slate-400 transition hover:text-slate-100 sm:block">Sign in</Link><Link to="/register" className="rounded-full bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 shadow-[0_0_24px_rgba(103,232,249,0.15)] transition hover:bg-cyan-200">Get started</Link><button type="button" onClick={() => setMenuOpen((open) => !open)} className="rounded-lg p-2 text-slate-400 md:hidden" aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen}>{menuOpen ? <X size={18} /> : <Menu size={18} />}</button></div>
    </div>
    {menuOpen && <nav className="mx-auto mt-3 flex max-w-7xl flex-col gap-1 rounded-2xl border border-white/10 bg-slate-900/95 p-3 md:hidden" aria-label="Mobile navigation">{publicLinks.map((link) => <Link key={link.to} to={link.to} onClick={() => setMenuOpen(false)} className="rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-white/5">{link.label}</Link>)}<Link to="/login" className="rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-white/5">Sign in</Link></nav>}
  </header>;
}

export function PublicLayout({ children }: { children: React.ReactNode }) {
  // (#4138 Phase 1): প্রতিটি পাবলিক পৃষ্ঠার নিচে থিম-সচেতন জীবন্ত স্তর —
  // অরব/কণার রঙ CSS vars অনুসরণ করে, তাই টগল করলেই ৮ থিমে রঙ বদলায়।
  // LiveBackground fixed+pointer-events-none — কনটেন্ট-ইন্টার‍্যাকশনে বাধা নেই।
  return <div className="relative min-h-screen bg-[#0d0f12] text-slate-100"><LiveBackground variant="public" />{children}</div>;
}

type Message = { role: 'user' | 'assistant'; text: string };
function responseFor(input: string) { const text = input.toLowerCase(); if (text.includes('plan') || text.includes('build')) return 'I can help turn that idea into a practical plan. Start with the outcome, then add the context and constraints that matter.'; if (text.includes('research')) return 'I can help structure the research, compare the important signals, and turn the findings into a clear next step.'; if (text.includes('file') || text.includes('document')) return 'That is a great use for SupremeAI. Sign in when you want to bring files into the conversation and keep source context attached.'; return 'I can help you think that through. Ask me to plan, explain, summarize, research, or turn an idea into your next action.'; }

function AssistantAvatar({ muted = false }: { muted?: boolean }) { return <span aria-hidden="true" className={`mt-1 flex size-6 shrink-0 items-center justify-center rounded-lg font-mono text-[10px] font-bold text-cyan-300 ${muted ? 'bg-cyan-300/[0.06]' : 'bg-cyan-300/10 shadow-[0_0_16px_rgba(103,232,249,0.15)]'}`}>S</span>; }

function AssistantBubble({ text }: { text: string }) { return <div className="animate-guest-bubble-in flex max-w-[85%] items-start gap-2.5"><AssistantAvatar /><p className="rounded-3xl rounded-tl-md border border-white/[0.06] bg-white/[0.04] px-5 py-3 text-sm leading-6 text-slate-300">{text}</p></div>; }

function TypingIndicator() { return <div className="animate-guest-bubble-in flex max-w-[85%] items-start gap-2.5" role="status" aria-label="Assistant is typing"><AssistantAvatar muted /><span className="flex items-center gap-1.5 rounded-3xl rounded-tl-md border border-white/[0.06] bg-white/[0.04] px-4 py-3.5"><span className="size-1.5 animate-bounce rounded-full bg-slate-500 [animation-delay:0ms]" /><span className="size-1.5 animate-bounce rounded-full bg-slate-500 [animation-delay:150ms]" /><span className="size-1.5 animate-bounce rounded-full bg-slate-500 [animation-delay:300ms]" /></span></div>; }

function ModelPicker({ onSelect }: { onSelect: (model: string) => void }) { const [open, setOpen] = React.useState(false); const [selected, setSelected] = React.useState(models[0]); return <div className="relative"><button type="button" onClick={() => setOpen((value) => !value)} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-slate-400 outline-none transition hover:bg-white/5 hover:text-slate-200 focus-visible:ring-2 focus-visible:ring-cyan-300/50" aria-expanded={open}> <span className="size-1.5 rounded-full bg-cyan-300" />{selected.name}<ChevronDown size={13} /></button>{open && <div className="animate-guest-menu-in absolute bottom-full right-0 mb-2 w-64 origin-bottom-right rounded-2xl border border-white/10 bg-[#171a20] p-2 shadow-2xl">{models.map((model) => <button key={model.name} type="button" onClick={() => { setSelected(model); onSelect(model.name); setOpen(false); }} className={`flex w-full items-start justify-between rounded-xl p-3 text-left outline-none transition hover:bg-white/5 focus-visible:bg-white/5 focus-visible:ring-2 focus-visible:ring-cyan-300/50 ${selected.name === model.name ? 'bg-white/[0.06] ring-1 ring-inset ring-cyan-300/25' : ''}`}><span><span className="block text-sm text-slate-200">{model.name}</span><span className="mt-1 block text-xs text-slate-500">{model.detail}</span></span><span className="text-[10px] text-cyan-300">{model.tag}</span></button>)}</div>}</div>; }

export function GuestChatPage() {
  const [messages, setMessages] = React.useState<Message[]>([]); const [input, setInput] = React.useState(''); const [model, setModel] = React.useState(models[0].name); const [typing, setTyping] = React.useState(false); const inputRef = React.useRef<HTMLTextAreaElement>(null); const typingTimer = React.useRef<number | null>(null);
  // Issue #1460/#1461: in-page auth prompt state (feature the guest tapped).
  const [authFeature, setAuthFeature] = React.useState<string | null>(null);
  React.useEffect(() => () => { if (typingTimer.current !== null) window.clearTimeout(typingTimer.current); }, []);
  const submit = (event?: React.FormEvent) => { event?.preventDefault(); const value = input.trim(); if (!value || typing) return; setMessages((current) => [...current, { role: 'user', text: value }]); setInput(''); setTyping(true); typingTimer.current = window.setTimeout(() => { setMessages((current) => [...current, { role: 'assistant', text: responseFor(value) }]); setTyping(false); inputRef.current?.focus(); }, 650); };
  const reset = () => { if (typingTimer.current !== null) window.clearTimeout(typingTimer.current); setTyping(false); setMessages([]); setInput(''); inputRef.current?.focus(); };
  // QA fix (2026-09-14): chips used to hard-replace the composer, so typed text
  // butted straight against the canned prompt ("...findings.What is..."). Now the
  // prompt is appended with a space and the composer keeps focus for continuation.
  const applyIntent = (prompt: string) => { setInput((current) => (current.trim() ? `${current.trimEnd()} ${prompt} ` : `${prompt} `)); inputRef.current?.focus(); };
  // Intent prompt styling: when a sent message starts with a canned prompt,
  // render the prefix dimmed so the user's own words lead visually.
  const renderUserText = (text: string) => { const hit = intents.find(({ prompt }) => text.startsWith(prompt)); if (!hit) return text; const rest = text.slice(hit.prompt.length); return (<><span className="text-slate-400">{hit.prompt}</span>{rest}</>); };
  return <PublicLayout><PublicHeader /><CapabilityStrip onProtected={setAuthFeature} /><main className="relative flex min-h-screen flex-col overflow-hidden px-4 pb-8 pt-28 sm:px-8"><div className="pointer-events-none absolute left-1/2 top-[48%] size-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-950/35 blur-3xl" aria-hidden="true" /><div className="pointer-events-none absolute left-1/2 top-[48%] size-[22rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-300/[0.06] blur-3xl" aria-hidden="true" /><section className="relative mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center"><div className="mb-7 transition-all duration-500" data-chat-start={messages.length === 0}>{messages.length === 0 ? <><div className="mx-auto mb-5 flex size-12 items-center justify-center rounded-2xl bg-cyan-300/10 text-cyan-300 shadow-[0_0_40px_rgba(103,232,249,0.1)]"><Sparkles size={23} aria-hidden="true" /></div><h1 className="text-balance text-center text-3xl font-medium tracking-tight text-slate-200 sm:text-5xl">What would you like to work on?</h1><p className="mx-auto mt-4 max-w-md text-center text-sm leading-6 text-slate-500">Start with a question. SupremeAI helps you find the right way forward.</p><div className="mt-8 flex flex-wrap justify-center gap-2">{intents.map(({ label, prompt, icon: Icon }) => <button key={label} type="button" onClick={() => applyIntent(prompt)} className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-slate-400 outline-none transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.05] hover:text-cyan-200 focus-visible:ring-2 focus-visible:ring-cyan-300/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0d0f12]"><Icon size={14} />{label}</button>)}</div></> : <div className="guest-thread-scroll mx-auto max-h-[38vh] max-w-2xl space-y-4 overflow-y-auto px-1 [scrollbar-gutter:stable]" aria-live="polite" aria-busy={typing}>{messages.map((message, index) => message.role === 'user' ? <div key={`${message.role}-${index}`} className="animate-guest-bubble-in ml-auto max-w-[85%] rounded-3xl rounded-tr-md bg-slate-800 px-5 py-3 text-sm leading-6 text-slate-100 shadow-[0_2px_12px_rgba(0,0,0,0.25)]">{renderUserText(message.text)}</div> : <AssistantBubble key={`${message.role}-${index}`} text={message.text} />)}{typing && <TypingIndicator />}</div>}</div><form onSubmit={submit} className="relative rounded-[1.65rem] border border-white/10 bg-[#202124] p-3 shadow-[0_18px_80px_rgba(0,0,0,0.3)] transition focus-within:border-cyan-300/35 focus-within:shadow-[0_0_45px_rgba(34,211,238,0.1)]" aria-label="Guest chat"><textarea ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) { event.preventDefault(); submit(); } }} rows={2} placeholder="Ask, write, research, or build..." className="min-h-14 w-full resize-none bg-transparent px-2 py-1 text-base leading-7 text-slate-100 outline-none placeholder:text-slate-600" aria-label="Message SupremeAI" /><div className="flex flex-wrap items-center justify-between gap-2 pt-2"><div className="flex items-center gap-1"><button type="button" onClick={() => setAuthFeature("file uploads")} title="Sign in to attach files" aria-label="Attach a file (requires sign-in)" className="rounded-full p-2 text-slate-500 outline-none transition hover:bg-white/10 hover:text-slate-300 active:scale-90 focus-visible:ring-2 focus-visible:ring-cyan-300/50"><Paperclip size={18} /></button><button type="button" onClick={reset} className="rounded-full p-2 text-slate-500 outline-none transition hover:bg-white/10 hover:text-slate-300 focus-visible:ring-2 focus-visible:ring-cyan-300/50" aria-label="Start a new chat"><Plus size={19} /></button><ModelPicker onSelect={setModel} /><span className="hidden text-xs text-slate-600 lg:inline">{model} · temporary session</span></div><button type="submit" disabled={!input.trim() || typing} className="flex size-9 items-center justify-center rounded-full bg-slate-100 text-slate-950 outline-none transition hover:bg-cyan-200 active:scale-90 focus-visible:ring-2 focus-visible:ring-cyan-300/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#202124] disabled:cursor-not-allowed disabled:opacity-30" aria-label="Send message"><ArrowUp size={18} /></button></div></form>{messages.length > 0 && <div className="mt-7 rounded-2xl border border-white/8 bg-white/[0.03] p-4 text-center"><p className="text-sm text-slate-400">Your conversation is temporary. Sign in to save it and keep working with more context.</p><div className="mt-4 flex flex-wrap justify-center gap-2">{capabilityItems.map(({ title, icon: Icon, text }) => <Link key={title} to="/register" className="flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-xs text-slate-400 outline-none transition hover:border-cyan-300/40 hover:text-cyan-200 focus-visible:border-cyan-300/40 focus-visible:text-cyan-200 focus-visible:ring-2 focus-visible:ring-cyan-300/50" title={text}><Icon size={14} />{title}</Link>)}<Link to="/register" className="flex items-center gap-2 rounded-full bg-cyan-300 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-cyan-200"><Check size={14} />Save this chat</Link></div></div>}</section><p className="relative mx-auto mt-6 max-w-2xl text-center text-xs leading-5 text-slate-600">SupremeAI can make mistakes. <Link to="/login" className="text-slate-400 underline underline-offset-4 hover:text-cyan-200">Sign in</Link> for saved history, files, tools, and extended conversations.</p></main>{authFeature && <AuthPromptModal feature={authFeature} onClose={() => setAuthFeature(null)} />}</PublicLayout>;
}

export function ModelsPage() { return <PublicLayout><PublicHeader /><main className="mx-auto max-w-6xl px-5 pb-24 pt-36 sm:px-8"><p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">Model intelligence</p><h1 className="mt-5 max-w-3xl text-balance text-4xl font-medium tracking-tight text-slate-100 sm:text-6xl">Choose the outcome. We help find the model.</h1><p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-500">Explore capability-first recommendations instead of navigating a wall of model names.</p><div className="mt-12 grid gap-3 md:grid-cols-3">{models.map((model) => <article key={model.name} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-cyan-300/30"><div className="flex items-center justify-between"><span className="size-2 rounded-full bg-cyan-300" /><span className="text-xs text-cyan-300">{model.tag}</span></div><h2 className="mt-10 font-medium text-slate-200">{model.name}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{model.detail}</p><Link to="/" className="mt-6 inline-flex items-center gap-2 text-sm text-slate-300 hover:text-cyan-200">Try in chat <ArrowUp size={14} className="rotate-45" /></Link></article>)}</div></main></PublicLayout>; }

const pageCopy: Record<string, { eyebrow: string; title: string; description: string }> = { '/contact': { eyebrow: 'Contact', title: 'Bring your hardest workflow.', description: 'Tell us what you want to make simpler and we will help you find the right starting point.' } };
export function PublicInfoPage({ kind }: { kind: '/features' | '/pricing' | '/docs' | '/about' | '/contact' }) { const copy = pageCopy[kind]; if (!copy) return null; return <PublicLayout><PublicHeader /><main className="mx-auto max-w-5xl px-5 pb-24 pt-36 sm:px-8"><p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">{copy.eyebrow}</p><h1 className="mt-5 max-w-3xl text-balance text-4xl font-medium tracking-tight text-slate-100 sm:text-6xl">{copy.title}</h1><p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-500">{copy.description}</p><div className="mt-14 grid gap-3 sm:grid-cols-3">{capabilityItems.map(({ title, text, icon: Icon, href }) => <Link key={title} to={href} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.04]"><Icon size={19} className="text-cyan-300" /><h2 className="mt-8 font-medium text-slate-200">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{text}</p><span className="mt-5 inline-flex text-xs text-cyan-300">Preview capability</span></Link>)}</div><Link to="/" className="mt-12 inline-flex items-center gap-2 rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-200">Try SupremeAI <ArrowUp size={16} className="rotate-45" /></Link></main></PublicLayout>; }

// Issue #1459/#1488: Pricing/Docs/About used to render the SAME generic body
// (only the heading differed) — audit-flagged as duplicate content. Each page
// now owns distinct, honest content.

export function FeaturesPage() {
  // Issue #1521 (HIGH): the audit asked for the full Tier-S feature showcase —
  // exactly the twelve capabilities the product ships. Every card maps to a
  // real, mounted surface (route or panel), no invented features.
  const featureSections = [
    { title: 'Share links', text: 'Publish any conversation as a read-only link. Viewers see the thread without touching your account.', icon: Share2 },
    { title: 'Reasoning you can inspect', text: 'The thinking panel streams step-by-step reasoning while the agent works — no black box.', icon: BrainCircuitCompat },
    { title: 'Artifacts, not walls of text', text: 'Runnable HTML, code, diagrams, and SVGs land in a dedicated panel you open beside the chat.', icon: FileCode2Compat },
    { title: 'Image upload', text: 'Drop in screenshots and images so answers are grounded in what you actually see.', icon: ImageIcon },
    { title: 'Slash commands', text: 'Type / in the composer to call structured commands without leaving the keyboard.', icon: Terminal },
    { title: 'Chat search', text: 'Cmd+K opens the search dialog across your saved conversations — pick up any thread instantly.', icon: Search },
    { title: 'Export', text: 'Take the whole conversation with you — export to clean markdown whenever you need it.', icon: Download },
    { title: 'Global memory', text: 'A memory panel keeps the facts that matter across sessions, visible and editable by you.', icon: Database },
    { title: 'Prompt templates', text: 'Save the prompts you reuse and fire them from the template library instead of retyping.', icon: LayoutTemplate },
    { title: 'Branch conversations', text: 'Fork any message into a new branch and explore alternatives without losing the original.', icon: GitBranchCompat },
    { title: 'Scheduled tasks', text: 'Put recurring work on a schedule — the agent runs it and keeps the results waiting for you.', icon: Clock },
    { title: 'Deep research', text: 'Launch multi-source research runs that compile findings into a structured report.', icon: Telescope },
  ];
  return <PublicLayout><PublicHeader /><main className="mx-auto max-w-6xl px-5 pb-24 pt-36 sm:px-8"><p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">Features</p><h1 className="mt-5 max-w-3xl text-balance text-4xl font-medium tracking-tight text-slate-100 sm:text-6xl">A simple conversation can become useful work.</h1><p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-500">Start with a question. Layer on context, tools, and repeatable workflows as your needs grow — all twelve Tier-S surfaces ship in the product today.</p><div className="mt-14 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{featureSections.map(({ title, text, icon: Icon }) => <section key={title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-cyan-300/30"><Icon size={19} className="text-cyan-300" aria-hidden="true" /><h2 className="mt-6 font-medium text-slate-200">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{text}</p></section>)}</div><Link to="/" className="mt-12 inline-flex items-center gap-2 rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-200">Try it in guest chat <ArrowUp size={16} className="rotate-45" /></Link></main></PublicLayout>;
}

// lucide import compatibility aliases (same icons, page-local names)
const BrainCircuitCompat = BrainCircuit;
const FileCode2Compat = FileCode2;
const GitBranchCompat = GitBranch;

export function PricingPage() {
  const tiers = [
    { name: 'Free', price: '$0', cadence: 'during early access', highlight: true, cta: { label: 'Start free', to: '/register' }, features: ['Guest and account chat', 'Conversation history', 'File uploads and context', 'Reasoning panel + artifacts'] },
    { name: 'Pro', price: 'Early access', cadence: 'pricing announced at launch', highlight: false, cta: { label: 'Join the waitlist', to: '/register' }, features: ['Higher rate limits', 'Team workspaces', 'Tool integrations', 'Priority support'] },
    { name: 'Enterprise', price: 'Custom', cadence: 'talk to us', highlight: false, cta: { label: 'Contact us', to: '/contact' }, features: ['SSO + audit logs', 'Tenant isolation', 'Deploy-gate governance', 'Dedicated support'] },
  ];
  return <PublicLayout><PublicHeader /><main className="mx-auto max-w-6xl px-5 pb-24 pt-36 sm:px-8"><p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">Plans</p><h1 className="mt-5 max-w-3xl text-balance text-4xl font-medium tracking-tight text-slate-100 sm:text-6xl">Start free, then scale with context.</h1><p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-500">Try the core conversation experience first. Create an account when you need history, files, tools, and longer-running work.</p><div className="mt-14 grid gap-4 lg:grid-cols-3">{tiers.map((tier) => <section key={tier.name} aria-label={`${tier.name} plan`} className={`flex flex-col rounded-3xl border p-7 ${tier.highlight ? 'border-cyan-300/40 bg-cyan-300/[0.05] shadow-[0_0_45px_rgba(34,211,238,0.08)]' : 'border-white/10 bg-white/[0.03]'}`}><div className="flex items-baseline justify-between"><h2 className="text-lg font-medium text-slate-100">{tier.name}</h2>{tier.highlight && <span className="rounded-full bg-cyan-300/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-200">Current phase</span>}</div><p className="mt-4 text-3xl font-semibold tracking-tight text-slate-100">{tier.price}</p><p className="mt-1 text-xs text-slate-500">{tier.cadence}</p><ul className="mt-6 flex-1 space-y-2.5">{tier.features.map((feature) => <li key={feature} className="flex items-start gap-2 text-sm leading-6 text-slate-400"><Check size={15} className="mt-1 shrink-0 text-cyan-300" aria-hidden="true" />{feature}</li>)}</ul><Link to={tier.cta.to} className={`mt-8 inline-flex items-center justify-center rounded-full px-5 py-2.5 text-sm font-semibold transition ${tier.highlight ? 'bg-cyan-300 text-slate-950 hover:bg-cyan-200' : 'border border-white/15 text-slate-200 hover:border-cyan-300/40'}`}>{tier.cta.label}</Link></section>)}</div><p className="mt-10 text-center text-xs text-slate-600">All plans include the guest experience. No credit card required during early access.</p><div className="mt-8 text-center"><Link to="/" className="inline-flex items-center gap-2 text-sm text-slate-300 transition hover:text-cyan-200">Try it in guest chat first <ArrowUp size={14} className="rotate-45" /></Link></div></main></PublicLayout>;
}

export function DocsPage() {
  // Issue #1523 (MEDIUM): the audit asked for a setup guide and an API
  // reference on this page — both are now first-class sections alongside the
  // topic clusters. Endpoints listed are the real, mounted contract surfaces.
  const docTopics = [
    { title: 'Context & memory', text: 'Attach files, search past conversations, and let the reasoning panel show its work.', items: ['File uploads', 'Chat search (Cmd+K)', 'Reasoning panel'] },
    { title: 'Power features', text: 'Slash commands, artifacts, branching, sharing, and export turn chats into durable work.', items: ['Slash commands', 'Artifacts panel', 'Branching & sharing'] },
    { title: 'Admin & operations', text: 'Command Center metrics, self-heal approvals, API keys, and tenant limits for operators.', items: ['Command Center overview', 'Admin API contract', 'Tenant limits'] },
  ];
  const setupSteps = [
    { step: '1', title: 'Try guest chat', text: 'Open the home page and ask a question — no account required.' },
    { step: '2', title: 'Create an account', text: 'Register to keep history, upload files, and unlock the workspace.' },
    { step: '3', title: 'Pick your surface', text: 'Use /chat for conversation, /research for deep runs, /scheduled-tasks for recurring work.' },
    { step: '4', title: 'Bring your tools', text: 'Connect integrations and generate API keys from /settings/api-keys.' },
  ];
  const apiEndpoints = [
    { method: 'GET', path: '/api/v1/health', note: 'Service health probe (public)' },
    { method: 'POST', path: '/api/v1/auth/login', note: 'Session login — sets the user token' },
    { method: 'POST', path: '/api/v1/auth/register', note: 'Account creation' },
    { method: 'POST', path: '/api/v1/stream/chat', note: 'Real-time chat entrypoint (SSE)' },
    { method: 'POST', path: '/api/chat/orchestrate', note: 'Conversation orchestration entrypoint' },
    { method: 'GET', path: '/api/preferences/', note: 'Per-tenant user preferences' },
    { method: 'GET', path: '/api/v1/conversations/', note: 'Conversation history (ai_memory read-projection)' },
    { method: 'GET', path: '/admin-api/metrics', note: 'Real rolling-window metrics (admin)' },
    { method: 'GET', path: '/admin-api/logs/stream', note: 'SSE log stream (admin)' },
  ];
  return <PublicLayout><PublicHeader /><main className="mx-auto max-w-6xl px-5 pb-24 pt-36 sm:px-8"><p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">Docs</p><h1 className="mt-5 max-w-3xl text-balance text-4xl font-medium tracking-tight text-slate-100 sm:text-6xl">From first question to governed execution.</h1><p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-500">Learn how guest chat, saved conversations, context, tools, and workspaces fit together.</p><div className="mt-14 grid gap-3 sm:grid-cols-2"><section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6"><h2 className="font-medium text-slate-200">Getting started</h2><p className="mt-2 text-sm leading-6 text-slate-500">Four steps from zero to a working workspace.</p><ol className="mt-5 space-y-4">{setupSteps.map(({ step, title, text }) => <li key={step} className="flex items-start gap-3"><span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-cyan-300/10 font-mono text-[11px] font-bold text-cyan-300">{step}</span><span><span className="block text-sm font-medium text-slate-300">{title}</span><span className="mt-0.5 block text-sm leading-6 text-slate-500">{text}</span></span></li>)}</ol></section>{docTopics.map(({ title, text, items }) => <section key={title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-6"><h2 className="font-medium text-slate-200">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{text}</p><ul className="mt-5 space-y-2">{items.map((item) => <li key={item} className="flex items-center gap-2 text-sm text-slate-400"><span className="size-1 rounded-full bg-cyan-300" aria-hidden="true" />{item}</li>)}</ul></section>)}</div><section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-6"><h2 className="font-medium text-slate-200">API reference</h2><p className="mt-2 text-sm leading-6 text-slate-500">The core HTTP contract. Admin endpoints require the admin session; all others require a bearer token after login.</p><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[34rem] border-collapse text-left text-sm"><thead><tr className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-500"><th className="py-2 pr-4 font-medium">Method</th><th className="py-2 pr-4 font-medium">Endpoint</th><th className="py-2 font-medium">Purpose</th></tr></thead><tbody>{apiEndpoints.map(({ method, path, note }) => <tr key={method + path} className="border-b border-white/[0.06] last:border-0"><td className="py-2.5 pr-4"><span className="rounded-md bg-cyan-300/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-cyan-300">{method}</span></td><td className="py-2.5 pr-4 font-mono text-xs text-slate-300">{path}</td><td className="py-2.5 text-slate-500">{note}</td></tr>)}</tbody></table></div></section><Link to="/" className="mt-12 inline-flex items-center gap-2 rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-200">Start with the product <ArrowUp size={16} className="rotate-45" /></Link></main></PublicLayout>;
}

export function AboutPage() {
  const principles = [
    { title: 'Honest signals', text: 'No fabricated metrics anywhere in the product. When the system does not know, it says so.' },
    { title: 'Approachable by default', text: 'The first message requires zero setup; depth is there when you reach for it.' },
    { title: 'Governed autonomy', text: 'Agents act inside policy: deploy gates, approvals, and audit trails are first-class.' },
  ];
  // Issue #1524 (MEDIUM): the audit asked for team info and the technology
  // stack — both now live on the page (mission + principles already did).
  const stack = [
    { layer: 'Frontend', text: 'React 18 + Vite single build (supremeai-studio-client), react-router, framer-motion, Tailwind design tokens, PWA service worker.' },
    { layer: 'Backend', text: 'FastAPI on Python — modular routers for auth, chat, memory, preferences, and the admin surface, with SSE streaming.' },
    { layer: 'Data', text: 'Firestore for durable tenant data, Redis-compatible caching at the edge, object storage for files and artifacts.' },
    { layer: 'Operations', text: 'Firebase Hosting + Vercel portals, Render-deployed API, CI-gated merges with a slot-based agent registry.' },
  ];
  const team = [
    { name: 'Saiful Haque Niloy', role: 'Project lead — architecture, product direction, and the governance model' },
    { name: 'The agent fleet', role: 'Slot-registered AI agents (agent-2, agent-7, agent-11, …) ship reviewed PRs against the public tracker' },
    { name: 'CI Doctor & vault-doctor', role: 'Automated guardians that track CI health and credential rotation in the open' },
  ];
  return <PublicLayout><PublicHeader /><main className="mx-auto max-w-5xl px-5 pb-24 pt-36 sm:px-8"><p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">About</p><h1 className="mt-5 max-w-3xl text-balance text-4xl font-medium tracking-tight text-slate-100 sm:text-6xl">AI that starts simple and grows with you.</h1><p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-500">SupremeAI makes intelligent work approachable at the first message and dependable at scale — a single conversation surface backed by observable, governed agents.</p><div className="mt-14 grid gap-3 sm:grid-cols-3">{principles.map(({ title, text }) => <section key={title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5"><h2 className="font-medium text-slate-200">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{text}</p></section>)}</div><div className="mt-6 grid gap-3 sm:grid-cols-2"><section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6"><h2 className="font-medium text-slate-200">Team</h2><ul className="mt-5 space-y-4">{team.map(({ name, role }) => <li key={name}><p className="text-sm font-medium text-slate-300">{name}</p><p className="mt-1 text-sm leading-6 text-slate-500">{role}</p></li>)}</ul></section><section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6"><h2 className="font-medium text-slate-200">Technology stack</h2><ul className="mt-5 space-y-4">{stack.map(({ layer, text }) => <li key={layer}><p className="text-sm font-medium text-slate-300">{layer}</p><p className="mt-1 text-sm leading-6 text-slate-500">{text}</p></li>)}</ul></section></div><div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-6"><h2 className="font-medium text-slate-200">Built in the open</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Development happens on GitHub with a public issue tracker, slot-based agent registry, and CI-gated merges. Every merge that touches you is traceable to a reviewed pull request.</p></div><Link to="/" className="mt-12 inline-flex items-center gap-2 rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-200">Meet your first agent <ArrowUp size={16} className="rotate-45" /></Link></main></PublicLayout>;
}
export default GuestChatPage;
