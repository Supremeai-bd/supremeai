// ============================================================================
// component >> MemoryBrowser.tsx
// project >> SupremeAI 2.0
// purpose >> Memory storage
// module >> src
// ============================================================================
import { Card, Badge, Skeleton } from '../ui';
import { Search, MessageSquare, Clock, Tag, Trash2 } from 'lucide-react';
import { useState } from 'react';

export function MemoryBrowser() {
  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => fetch('/memory/conversations').then(r => r.json()),
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedConv, setSelectedConv] = useState<any | null>(null);

  const filtered = conversations?.filter((c: any) =>
    c.topic?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.summary?.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030508]">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          🧠 Memory & Knowledge
        </h2>
        <Badge variant="purple">RAG ENABLED</Badge>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-1">
          <div className="flex gap-2 mb-4">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-2 text-slate-500" />
              <input
                type="text"
                placeholder="Search memories..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full bg-[#06080b] border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white outline-none focus:border-[#00f3ff] font-mono"
              />
            </div>
          </div>

          <div className="flex flex-col gap-2 max-h-[60vh] overflow-y-auto">
            {isLoading ? (
              <><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></>
            ) : filtered.length === 0 ? (
              <div className="text-xs text-slate-500 font-mono p-4 text-center">No conversations found.</div>
            ) : (
              filtered.map((conv: any) => (
                <button
                  key={conv.id}
                  onClick={() => setSelectedConv(conv)}
                  className={`text-left p-3 rounded-lg border transition-all ${
                    selectedConv?.id === conv.id
                      ? 'border-[#00f3ff]/50 bg-[#00f3ff]/10'
                      : 'border-slate-800 bg-slate-900/30 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-white font-mono">{conv.session_id}</span>
                    <span className="text-[9px] text-slate-500 font-mono">{conv.timestamp}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 line-clamp-2">{conv.summary}</div>
                  <div className="flex gap-1 mt-2">
                    {conv.tags?.map((tag: string) => (
                      <span key={tag} className="px-1 py-0.5 text-[9px] rounded bg-slate-800 text-slate-300 font-mono">{tag}</span>
                    ))}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="xl:col-span-2">
          {selectedConv ? (
            <Card title={`Session: ${selectedConv.session_id}`}>
              <div className="text-[10px] text-slate-500 mb-3 font-mono flex items-center gap-3">
                <span className="flex items-center gap-1"><Clock size={10} /> {selectedConv.timestamp}</span>
                <span className="flex items-center gap-1"><MessageSquare size={10} /> {selectedConv.turns} turns</span>
                <span className="flex items-center gap-1"><Tag size={10} /> {selectedConv.tags?.length} tags</span>
              </div>
              <div className="flex flex-col gap-3">
                {selectedConv.messages?.map((m: any, i: number) => (
                  <div key={i} className={`p-3 rounded-lg border text-xs font-mono ${
                    m.role === 'user' ? 'border-[#00f3ff]/30 bg-[#00f3ff]/5 text-white' : 'border-slate-800 bg-slate-900/30 text-slate-400'
                  }`}>
                    <div className="text-[9px] text-slate-500 mb-1 uppercase">{m.role}</div>
                    {m.content}
                  </div>
                ))}
              </div>
              <div className="flex justify-between items-center mt-4 pt-3 border-t border-slate-800">
                <div className="text-[10px] text-slate-500">Importance score: <span className="text-emerald-400 font-mono">{selectedConv.importance || 0.85}</span></div>
                <div className="flex gap-2">
                  <button className="text-[10px] text-slate-400 hover:text-white font-mono">Export</button>
                  <button className="text-[10px] text-red-400 hover:text-red-300 font-mono flex items-center gap-1"><Trash2 size={10} /> Purge</button>
                </div>
              </div>
            </Card>
          ) : (
            <div className="h-full flex items-center justify-center p-8 border border-dashed border-slate-800 rounded-xl">
              <div className="text-center">
                <MessageSquare size={32} className="mx-auto text-slate-700 mb-3" />
                <div className="text-xs text-slate-500 font-mono">Select a conversation to view details</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
