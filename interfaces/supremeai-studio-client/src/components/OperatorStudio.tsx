import Editor from '@monaco-editor/react';
import type { ChatMessage } from '../types';

interface OperatorStudioProps {
  code: string;
  setCode: (code: string) => void;
  customerMessages: ChatMessage[];
  customerInput: string;
  setCustomerInput: (val: string) => void;
  loading: boolean;
  handleSendCustomer: () => void;
}

export function OperatorStudio({
  code,
  setCode,
  customerMessages,
  customerInput,
  setCustomerInput,
  loading,
  handleSendCustomer
}: OperatorStudioProps) {
  return (
    <div className="flex-1 flex flex-row overflow-hidden">
      {/* Quick Presets Sidebar */}
      <div className="w-72 flex-shrink-0 bg-[#08090d]/60 backdrop-blur-lg border-r border-[rgba(138,92,246,0.15)] flex flex-col p-4 z-10">
        <div className="text-[11px] uppercase tracking-[2px] text-[#bc13fe] font-semibold mb-3">
          Quick Presets
        </div>
        <div className="flex-grow overflow-y-auto flex flex-col gap-3">
          <div 
            onClick={() => setCustomerInput('Python binary search algorithm design')}
            className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3 text-xs cursor-pointer hover:border-[#bc13fe]/30 hover:bg-[#bc13fe]/5 transition-all duration-300"
          >
            <strong className="text-[#f8f9fa] block mb-1">Code Generator</strong>
            <span className="text-slate-400 text-[11px]">Python binary search algorithm</span>
          </div>
          <div 
            onClick={() => setCustomerInput('Translate \'Welcome to SupremeAI\' to Bengali')}
            className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3 text-xs cursor-pointer hover:border-[#bc13fe]/30 hover:bg-[#bc13fe]/5 transition-all duration-300"
          >
            <strong className="text-[#f8f9fa] block mb-1">Translator</strong>
            <span className="text-slate-400 text-[11px]">Translate to Bengali</span>
          </div>
          <div 
            onClick={() => setCustomerInput('Write a marketing email for an AI startup')}
            className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3 text-xs cursor-pointer hover:border-[#bc13fe]/30 hover:bg-[#bc13fe]/5 transition-all duration-300"
          >
            <strong className="text-[#f8f9fa] block mb-1">Content Writer</strong>
            <span className="text-slate-400 text-[11px]">Startup marketing email</span>
          </div>
        </div>
        
        <div className="mt-4 p-3 bg-[#bc13fe]/5 border border-[#bc13fe]/20 rounded-lg flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-[#bc13fe] animate-pulse"></span>
          <span className="text-xs font-semibold text-slate-300">Operator Core Ready</span>
        </div>
      </div>

      {/* Monaco Editor Component */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="h-10 bg-[#090b11] border-b border-slate-800 flex items-center px-4">
          <span className="text-xs bg-[#161a27] text-[#00f3ff] border border-[#00f3ff]/20 px-3 py-1 rounded-t-md font-mono">
            main.js
          </span>
        </div>
        <div className="flex-1 relative">
          <Editor
            height="100%"
            defaultLanguage="javascript"
            theme="vs-dark"
            value={code}
            onChange={(val) => setCode(val || '')}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              fontFamily: "'JetBrains Mono', monospace",
              lineHeight: 24,
              padding: { top: 16 },
              scrollBeyondLastLine: false,
              smoothScrolling: true,
              cursorBlinking: 'smooth',
              cursorSmoothCaretAnimation: 'on'
            }}
          />
        </div>
      </div>

      {/* AI Partner Sidechat */}
      <div className="w-96 flex-shrink-0 bg-[#050608]/90 border-l border-slate-800 flex flex-col">
        <div className="h-10 border-b border-slate-800 flex items-center px-4 justify-between bg-[#0a0c12]">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider">SupremeAI Chat</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950/30 text-emerald-400 border border-emerald-900/30 font-mono">ONLINE</span>
        </div>
        <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
          {customerMessages.map(msg => (
            <div key={msg.id} className={`max-w-[85%] flex flex-col gap-1 ${msg.sender === 'user' ? 'self-end items-end' : 'self-start'}`}>
              <div className={`p-3.5 rounded-2xl text-[13.5px] leading-relaxed ${
                msg.sender === 'user' 
                  ? 'bg-gradient-to-br from-[#bc13fe] to-[#8b5cf6] text-white rounded-tr-none shadow-[0_4px_15px_rgba(188,19,254,0.2)]'
                  : 'bg-[#12141c]/80 border border-[rgba(138,92,246,0.15)] text-slate-200 rounded-tl-none'
              }`}>
                {msg.text}
              </div>
              <span className="text-[9px] text-slate-500 px-1">{msg.timestamp}</span>
            </div>
          ))}
          {loading && (
            <div className="text-xs text-slate-500 animate-pulse font-mono flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-[#bc13fe] rounded-full animate-bounce"></span>
              SupremeAI is thinking...
            </div>
          )}
        </div>
        <div className="p-4 border-t border-slate-800 bg-[#050608]">
          <div className="flex gap-2">
            <input 
              type="text"
              placeholder="Ask anything or generate code..."
              value={customerInput}
              onChange={e => setCustomerInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendCustomer()}
              className="flex-grow bg-[#0c0d13] border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#bc13fe] transition-colors"
            />
            <button 
              onClick={handleSendCustomer}
              className="bg-[#bc13fe] hover:bg-[#8b5cf6] text-white px-4 rounded-xl font-bold transition-all shadow-[0_4px_12px_rgba(188,19,254,0.2)] text-xs uppercase"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
