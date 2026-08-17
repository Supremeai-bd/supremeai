import React from 'react';
import { GitBranch, Shield, Lock, Unlock, Server, Cloud, Cpu, Layers } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════════
// AETHEL Desktop Studio — Multi-Workspace Fleet Canvas (100+ Repos Visual Node Graph)
// বাংলা মন্তব্য: ১০০+ রেজিস্টার্ড টার্গেট রেপো ও প্ল্যাটফর্মের ড্র্যাগ-অ্যান্ড-ড্রপ ভিজ্যুয়াল গ্রাফ
// ═══════════════════════════════════════════════════════════════════════════

interface TargetNode {
  id: string;
  name: string;
  type: 'github' | 'gcp' | 'render' | 'vercel' | 'firebase';
  scope: 'READ_ONLY' | 'FULL_CONTROL';
  status: 'active' | 'syncing' | 'idle';
}

const SAMPLE_NODES: TargetNode[] = [
  { id: '1', name: 'main-repository (Admin Owner)', type: 'github', scope: 'READ_ONLY', status: 'active' },
  { id: '2', name: 'agent-workspace (SupremeAI Managed)', type: 'github', scope: 'FULL_CONTROL', status: 'syncing' },
  { id: '3', name: 'supremeai-backend (GCP Cloud Run)', type: 'gcp', scope: 'FULL_CONTROL', status: 'active' },
  { id: '4', name: 'studio-client (Vercel Prod)', type: 'vercel', scope: 'FULL_CONTROL', status: 'idle' },
];

export const MultiWorkspaceCanvas: React.FC = () => {
  return (
    <div className="w-full h-full bg-[#050711] border border-white/10 rounded-2xl p-6 relative overflow-hidden font-sans">
      {/* Visual Canvas Background Grid */}
      <div className="absolute inset-0 bg-[radial-[#00f3ff]/5_1px,transparent_1px] [background-size:24px_24px] opacity-40 pointer-events-none" />

      <div className="flex items-center justify-between mb-6 relative z-10">
        <div>
          <h2 className="text-base font-mono font-bold uppercase tracking-wider text-[#00f3ff] flex items-center gap-2">
            <Layers size={18} />
            <span>Multi-Platform Target Fleet Canvas</span>
          </h2>
          <p className="text-xs text-gray-400 font-mono mt-1">
            Dynamic repository binding & real-time permission scope map (100+ Connected Nodes)
          </p>
        </div>
        <div className="flex gap-2">
          <span className="text-xs font-mono px-3 py-1 rounded-lg bg-[#00f3ff]/10 text-[#00f3ff] border border-[#00f3ff]/30">
            4 Targets Connected
          </span>
        </div>
      </div>

      {/* Target Node Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 relative z-10">
        {SAMPLE_NODES.map((node) => (
          <div
            key={node.id}
            className={`p-4 rounded-xl border transition-all duration-300 ${
              node.scope === 'READ_ONLY'
                ? 'bg-[#bc13fe]/5 border-[#bc13fe]/30 hover:shadow-[0_0_20px_rgba(188,19,254,0.3)]'
                : 'bg-[#00f3ff]/5 border-[#00f3ff]/30 hover:shadow-[0_0_20px_rgba(0,243,255,0.3)]'
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-bold text-gray-300 flex items-center gap-1.5">
                <GitBranch size={14} className="text-[#00f3ff]" />
                {node.name}
              </span>
              {node.scope === 'READ_ONLY' ? (
                <span className="flex items-center gap-1 text-[10px] font-mono font-bold text-[#bc13fe] bg-[#bc13fe]/10 px-2 py-0.5 rounded-md border border-[#bc13fe]/30">
                  <Lock size={10} /> READ_ONLY
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[10px] font-mono font-bold text-[#00f3ff] bg-[#00f3ff]/10 px-2 py-0.5 rounded-md border border-[#00f3ff]/30">
                  <Unlock size={10} /> FULL_CONTROL
                </span>
              )}
            </div>

            <div className="flex items-center justify-between text-[11px] font-mono text-gray-400 mt-4">
              <span>Platform: {node.type.toUpperCase()}</span>
              <span className="text-[#10b981] flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" />
                {node.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
