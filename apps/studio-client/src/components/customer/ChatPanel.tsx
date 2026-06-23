// ============================================================================
// component >> ChatPanel.tsx
// project >> SupremeAI 2.0
// purpose >> Chat interface
// module >> src
// ============================================================================
import { ActionCard } from '../admin/ActionCard';

interface ChatPanelProps {
  messages: ChatMessage[];
  input: string;
  onInputChange: (val: string) => void;
  onSend: () => void;
  loading: boolean;
  onSaveToProject?: (code: string) => void;
}

export function ChatPanel({ messages, input, onInputChange, onSend, loading, onSaveToProject }: ChatPanelProps) {
  return (
    <div className="w-96 flex-shrink-0 bg-[#050608]/90 border-l border-slate-800 flex flex-col">
      <div className="h-10 border-b border-slate-800 flex items-center px-4 justify-between bg-[#0a0c12]">
        <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider">SupremeAI Chat</span>
        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950/30 text-emerald-400 border border-emerald-900/30 font-mono">ONLINE</span>
      </div>
      <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
        {messages.map(msg => (
          <div key={msg.id} className={`max-w-[85%] flex flex-col gap-1 ${msg.sender === 'user' ? 'self-end items-end' : 'self-start w-full'}`}>
            <div className={`p-3.5 rounded-2xl text-[13.5px] leading-relaxed ${
              msg.sender === 'user'
                ? 'bg-gradient-to-br from-[#bc13fe] to-[#8b5cf6] text-white rounded-tr-none shadow-[0_4px_15px_rgba(188,19,254,0.2)]'
                : 'bg-[#12141c]/80 border border-[rgba(138,92,246,0.15)] text-slate-200 rounded-tl-none'
            }`}>
              {msg.sender === 'user' ? (
                msg.text
              ) : (
                <ActionCard rawContent={msg.text} onSaveToProject={onSaveToProject} />
              )}
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
            value={input}
            onChange={e => onInputChange(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onSend()}
            className="flex-grow bg-[#0c0d13] border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#bc13fe] transition-colors"
          />
          <button
            onClick={onSend}
            className="bg-[#bc13fe] hover:bg-[#8b5cf6] text-white px-4 rounded-xl font-bold transition-all shadow-[0_4px_12px_rgba(188,19,254,0.2)] text-xs uppercase"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
