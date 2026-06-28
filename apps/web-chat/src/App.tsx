// apps/web-chat/src/App.tsx
import { useState, useEffect, useRef } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'স্বাগতম! আমি আপনার পার্সোনাল এআই অ্যাসিস্ট্যান্ট। আমাকে যেকোনো টাস্ক বা নির্দেশ দিন।',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeSkill, setActiveSkill] = useState<string | null>(null);
  const [language, setLanguage] = useState<'bn' | 'en'>('bn');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [quotaRemaining, setQuotaRemaining] = useState(87); // ৮৭% টোকেন কোটা বাকি
  const chatAreaRef = useRef<HTMLDivElement>(null);

  // বাংলা মন্তব্য: চ্যাট মেসেজ বাড়ার সাথে সাথে স্ক্রোলিং ডাউন করার ইফেক্ট
  useEffect(() => {
    const el = chatAreaRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // বাংলা মন্তব্য: ব্যাকএন্ডে রিকোয়েস্ট পাঠিয়ে চ্যাট মেসেজ প্রসেস করা
  const sendMessage = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text) return;
    setInput('');

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);

    const typingMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: language === 'bn' ? 'প্রসেস করা হচ্ছে...' : 'Processing neural pipeline...',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, typingMsg]);
    setLoading(true);

    try {
      const response = await fetch('/task/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: text,
          task_type: text.toLowerCase().includes('code') ? 'coding' : 'general',
        }),
      });
      const data = await response.json() as { result?: string };
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingMsg.id ? { ...m, content: data.result || 'No response generated.' } : m
        )
      );
      // টোকেন কোটা কমানো (সিমুলেশন)
      setQuotaRemaining(prev => Math.max(prev - 2, 0));
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingMsg.id ? { ...m, content: language === 'bn' ? 'সার্ভার সংযোগে ত্রুটি ঘটেছে।' : 'Neural connection pipeline error.' } : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // বাংলা মন্তব্য: ড্র্যাগ-অ্যান্ড-ড্রপ নোড হ্যান্ডলিং স্ট্যাটাস
  const handleNodeClick = (skillName: string) => {
    setActiveSkill(skillName);
    setInput(prev => prev ? `${prev} using ${skillName}` : `Activate ${skillName} task: `);
  };

  const toggleVoice = () => {
    setIsSpeaking(!isSpeaking);
    if (!isSpeaking) {
      setTimeout(() => {
        setIsSpeaking(false);
        sendMessage(language === 'bn' ? 'কোড আর্কিটেক্ট রান করো' : 'Activate Code Architect');
      }, 3000);
    }
  };

  return (
    <div className={`flex w-screen h-screen overflow-hidden font-sans transition-colors duration-300 ${
      theme === 'dark' ? 'bg-[#030712] text-slate-100' : 'bg-slate-50 text-slate-900'
    }`}>
      
      {/* বাম এবং মধ্য অংশ: সায়েন্স-ফিকশন ফ্লোটিং নেটওয়ার্ক নোড ডিজাইন */}
      <div className="flex-1 flex flex-col relative overflow-hidden p-6 border-r border-[#00f3ff]/10">
        
        {/* টপ স্ট্যাটাস বার */}
        <div className="flex justify-between items-center z-10">
          <div>
            <h1 className="text-lg font-black tracking-widest text-[#00f3ff] uppercase">// SUPREME WORKSPACE</h1>
            <p className="text-[10px] text-slate-500 font-mono">Autonomic Personal Node client</p>
          </div>
          <div className="flex gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse mt-1.5" />
            <span className="text-[11px] font-mono text-slate-400">Node Sync: Nominal</span>
          </div>
        </div>

        {/* কেন্দ্রীয় ফ্লোটিং কোর এবং নোডস (Aethel Client Canvas) */}
        <div className="flex-1 flex items-center justify-center relative">
          
          {/* সেন্ট্রাল অরবিটাল কোর (AI Assistant Core) */}
          <div 
            onClick={() => handleNodeClick('AI Assistant Core')}
            className="z-20 cursor-pointer flex flex-col items-center justify-center p-6 rounded-full border border-[#00f3ff]/30 bg-slate-950/80 shadow-[0_0_40px_rgba(0,243,255,0.15)] hover:shadow-[0_0_60px_rgba(0,243,255,0.35)] transition-all hover:scale-105 w-[180px] h-[180px]"
          >
            <div className="w-[120px] h-[120px] rounded-full border-2 border-dashed border-[#00f3ff]/60 flex items-center justify-center animate-spin" style={{ animationDuration: '25s' }}>
              <div className="w-[90px] h-[90px] rounded-full border border-double border-[#00ff66]/60 bg-gradient-to-tr from-[#00f3ff]/10 to-[#00ff66]/10 flex items-center justify-center">
                <div className="w-[50px] h-[50px] rounded-full bg-[#00f3ff] shadow-[0_0_20px_#00f3ff] flex items-center justify-center text-slate-950 font-black">
                  A
                </div>
              </div>
            </div>
            <span className="text-[10px] font-mono text-[#00f3ff] mt-3 tracking-widest font-black uppercase">Assistant Core</span>
          </div>

          {/* ভাসমান নোডসমূহ (Floating Nodes) */}
          {/* ১. Code Architect */}
          <div 
            draggable 
            onClick={() => handleNodeClick('Code Architect')}
            className="absolute top-[10%] left-[15%] z-10 cursor-pointer p-3 rounded-lg border border-[#00f3ff]/20 bg-slate-950/90 text-[10px] font-mono hover:border-[#00f3ff] hover:shadow-[0_0_15px_rgba(0,243,255,0.2)] transition-all active:scale-95"
          >
            <div className="font-bold text-[#00f3ff]">💻 Code Architect</div>
            <div className="text-[8px] text-slate-500 mt-0.5">Code and repo agent</div>
          </div>

          {/* ২. Data Analyzer */}
          <div 
            draggable 
            onClick={() => handleNodeClick('Data Analyzer')}
            className="absolute top-[12%] right-[15%] z-10 cursor-pointer p-3 rounded-lg border border-[#00ff66]/20 bg-slate-950/90 text-[10px] font-mono hover:border-[#00ff66] hover:shadow-[0_0_15px_rgba(0,255,102,0.2)] transition-all active:scale-95"
          >
            <div className="font-bold text-[#00ff66]">📊 Data Analyzer</div>
            <div className="text-[8px] text-slate-500 mt-0.5">PDF/Excel insights</div>
          </div>

          {/* ৩. Web Researcher */}
          <div 
            draggable 
            onClick={() => handleNodeClick('Web Researcher')}
            className="absolute bottom-[25%] left-[10%] z-10 cursor-pointer p-3 rounded-lg border border-[#ffbd2e]/20 bg-slate-950/90 text-[10px] font-mono hover:border-[#ffbd2e] hover:shadow-[0_0_15px_rgba(255,189,46,0.2)] transition-all active:scale-95"
          >
            <div className="font-bold text-[#ffbd2e]">🔍 Web Researcher</div>
            <div className="text-[8px] text-slate-500 mt-0.5">Live crawling research</div>
          </div>

          {/* ৪. Content & Voice */}
          <div 
            draggable 
            onClick={() => handleNodeClick('Content & Voice')}
            className="absolute bottom-[25%] right-[10%] z-10 cursor-pointer p-3 rounded-lg border border-[#00f3ff]/20 bg-slate-950/90 text-[10px] font-mono hover:border-[#00f3ff] hover:shadow-[0_0_15px_rgba(0,243,255,0.2)] transition-all active:scale-95"
          >
            <div className="font-bold text-[#00f3ff]">🎙️ Content & Voice</div>
            <div className="text-[8px] text-slate-500 mt-0.5">Bangla TTS & Copy</div>
          </div>

          {/* ৫. My Workspace */}
          <div 
            draggable 
            onClick={() => handleNodeClick('My Workspace')}
            className="absolute top-[48%] left-[5%] z-10 cursor-pointer p-3 rounded-lg border border-slate-800 bg-slate-950/90 text-[10px] font-mono hover:border-slate-500 hover:shadow-[0_0_15px_rgba(255,255,255,0.05)] transition-all active:scale-95"
          >
            <div className="font-bold text-slate-300">📁 My Workspace</div>
            <div className="text-[8px] text-slate-500 mt-0.5">Saved context maps</div>
          </div>

        </div>

        {/* বটম ইউটিলিটি বার */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-center bg-slate-950/80 border border-slate-900 p-4 rounded-xl z-10">
          
          {/* Preferences button */}
          <button 
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="flex items-center justify-center gap-2 py-2 px-3 rounded bg-slate-900/60 border border-slate-800 hover:border-[#00f3ff]/50 text-slate-300 hover:text-white transition-all font-mono text-xs"
          >
            ⚙️ {theme === 'dark' ? 'LIGHT THEME' : 'DARK THEME'}
          </button>

          {/* Skill Store button */}
          <button 
            onClick={() => setLanguage(language === 'bn' ? 'en' : 'bn')}
            className="flex items-center justify-center gap-2 py-2 px-3 rounded bg-slate-900/60 border border-slate-800 hover:border-[#00ff66]/50 text-slate-300 hover:text-white transition-all font-mono text-xs"
          >
            🛍️ LANG: {language === 'bn' ? 'বাংলা' : 'ENGLISH'}
          </button>

          {/* Voice Waveform (মাঝখানে) */}
          <div className="md:col-span-2 flex items-center justify-between gap-3 px-4 py-1.5 rounded-lg bg-[#00f3ff]/5 border border-[#00f3ff]/20 shadow-[0_0_15px_rgba(0,243,255,0.05)]">
            <div className="flex items-center gap-2" onClick={toggleVoice}>
              <div className={`w-2.5 h-2.5 rounded-full ${isSpeaking ? 'bg-rose-500 animate-ping' : 'bg-[#00f3ff]'}`} />
              <span className="text-[10px] font-mono text-slate-300">
                {isSpeaking ? "Speaking..." : "Voice Command Bar"}
              </span>
            </div>
            {isSpeaking && (
              <div className="flex items-center gap-1">
                <span className="w-1 h-3 bg-rose-500 animate-pulse"></span>
                <span className="w-1 h-5 bg-rose-500 animate-pulse delay-75"></span>
                <span className="w-1 h-4 bg-rose-500 animate-pulse delay-150"></span>
              </div>
            )}
            <div className="text-[9px] font-mono text-slate-400">
              🔋 Quota: {quotaRemaining}% remaining
            </div>
          </div>

        </div>

      </div>

      {/* ডানদিকের গ্লাসমরফিজম প্যানেল: অ্যাক্টিভ চ্যাট ও কোড এডিটর */}
      <div className="w-full lg:w-[420px] flex flex-col bg-slate-950/40 backdrop-blur-2xl border-l border-[#00f3ff]/10 p-4 h-full">
        
        <div className="border-b border-[#00f3ff]/10 pb-3 mb-4 flex justify-between items-center">
          <div>
            <h3 className="text-xs font-black tracking-widest text-[#00f3ff] font-mono uppercase">// Chat & Agent Editor</h3>
            <p className="text-[9px] text-slate-500 font-mono">Live neural feedback responses</p>
          </div>
          {activeSkill && (
            <span className="text-[9px] px-2 py-0.5 rounded bg-[#00f3ff]/10 border border-[#00f3ff]/30 text-[#00f3ff] font-mono">
              {activeSkill}
            </span>
          )}
        </div>

        {/* চ্যাট মেসেজেস লিস্ট */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-1 mb-4" ref={chatAreaRef}>
          {messages.map(msg => (
            <div key={msg.id} className={`flex flex-col max-w-[85%] ${
              msg.role === 'user' ? 'ml-auto items-end' : 'mr-auto'
            }`}>
              <div className={`p-3 rounded-lg text-xs leading-relaxed ${
                msg.role === 'user' 
                  ? 'bg-[#00f3ff] text-slate-950 font-bold shadow-[0_4px_12px_rgba(0,243,255,0.15)]' 
                  : 'bg-slate-900/80 border border-slate-800 text-slate-200'
              }`}>
                {msg.content}
              </div>
              <span className="text-[9px] text-slate-500 font-mono mt-1 px-1">
                {msg.timestamp.toLocaleTimeString()}
              </span>
            </div>
          ))}
          {loading && (
            <div className="text-[10px] text-[#00ff66] font-mono flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-[#00ff66] rounded-full animate-bounce"></span>
              Thinking...
            </div>
          )}
        </div>

        {/* ইনপুট ফিল্ড */}
        <div className="border-t border-[#00f3ff]/10 pt-4 bg-slate-950/20">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Ask anything (e.g., 'write a python binary search')..."
              className="flex-grow bg-[#07090f] border border-slate-800 rounded-lg px-4 py-2.5 text-xs text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              onClick={() => sendMessage()}
              disabled={loading}
              className="bg-[#00f3ff] hover:bg-cyan-400 text-black font-bold px-4 py-2.5 rounded-lg text-xs transition-all font-mono"
            >
              SEND
            </button>
          </div>
        </div>

      </div>

    </div>
  );
}

export default App;
