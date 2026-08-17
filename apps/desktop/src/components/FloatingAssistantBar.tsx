import React, { useState } from 'react';
import { Sparkles, Terminal, Shield, Zap, Search, X } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════════
// AETHEL Desktop Studio — Global Floating AI Assistant (Alt + Space Widget)
// বাংলা মন্তব্য: ভাসমান গ্লোবাল এআই সহায়ক বিজু যা যেকোনো স্ক্রিনের উপর সচল থাকে
// ═══════════════════════════════════════════════════════════════════════════

interface FloatingAssistantBarProps {
  onClose?: () => void;
}

export const FloatingAssistantBar: React.FC<FloatingAssistantBarProps> = ({ onClose }) => {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    // Simulate high-speed local/cloud AI routing
    setTimeout(() => {
      setResponse(`[SupremeAI Engine]: "${prompt}" এর জন্য অপটিমাইজড কোড সলিউশন রেডি করা হয়েছে। ২ টি ফাইল আপডেট প্রস্তাবিত।`);
      setLoading(false);
    }, 600);
  };

  return (
    <div className="fixed top-12 left-1/2 -translate-x-1/2 w-[680px] bg-[#080b14]/90 backdrop-blur-xl border border-[#00f3ff]/30 rounded-2xl shadow-[0_0_40px_rgba(0,243,255,0.25)] p-4 text-white z-50 transition-all font-sans">
      <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#00f3ff] to-[#bc13fe] flex items-center justify-center shadow-[0_0_10px_#00f3ff]">
            <Sparkles size={16} className="text-black" />
          </div>
          <span className="text-xs font-mono font-bold uppercase tracking-widest text-[#00f3ff]">
            SupremeAI Floating Assistant
          </span>
          <span className="text-[10px] bg-[#00f3ff]/10 text-[#00f3ff] px-2 py-0.5 rounded-full border border-[#00f3ff]/30 font-mono">
            Alt + Space
          </span>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X size={16} />
          </button>
        )}
      </div>

      <form onSubmit={handleSubmit} className="relative flex items-center">
        <Search size={18} className="absolute left-3 text-[#00f3ff]" />
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ask AI anything, generate code, or execute command..."
          className="w-full bg-black/40 border border-white/10 rounded-xl pl-10 pr-24 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#00f3ff] transition-all font-mono"
          autoFocus
        />
        <button
          type="submit"
          disabled={loading}
          className="absolute right-2 bg-gradient-to-r from-[#00f3ff] to-[#bc13fe] text-black font-bold text-xs px-4 py-2 rounded-lg hover:opacity-90 transition-opacity flex items-center gap-1"
        >
          {loading ? <Zap size={14} className="animate-spin" /> : <Zap size={14} />}
          <span>Run</span>
        </button>
      </form>

      {response && (
        <div className="mt-3 p-3 rounded-xl bg-black/60 border border-[#bc13fe]/30 text-xs font-mono text-gray-200">
          <p>{response}</p>
        </div>
      )}
    </div>
  );
};
