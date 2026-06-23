// ============================================================================
// component >> ConstitutionalRules.tsx
// project >> SupremeAI 2.0
// purpose >> Rules management
// module >> src
// ============================================================================
export function ConstitutionalRules({ rulesJson, setRulesJson, saveStatus, handleSaveRules }: ConstitutionalRulesProps) {
  return (
    <div className="flex-grow flex flex-col bg-[#050608]">
      <div className="h-8 border-b border-slate-850 bg-[#0c0f17] px-4 flex items-center justify-between">
        <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase font-mono">Constitutional Rules</span>
        <div className="flex items-center gap-3">
          {saveStatus && <span className="text-[10px] text-slate-400 font-mono">{saveStatus}</span>}
          <button
            onClick={handleSaveRules}
            className="bg-emerald-500 hover:bg-emerald-400 text-black text-[10px] font-bold px-2 py-0.5 rounded transition-colors font-mono uppercase"
          >
            Apply
          </button>
        </div>
      </div>
      <div className="flex-1 p-3">
        <textarea
          className="w-full h-full bg-black/40 border border-slate-900 rounded-lg p-4 text-[#00ff66] font-mono text-xs leading-relaxed outline-none resize-none focus:border-[#00f3ff]/30 focus:shadow-[0_0_15px_rgba(0,243,255,0.05)] transition-all"
          spellCheck="false"
          value={rulesJson}
          onChange={e => setRulesJson(e.target.value)}
        />
      </div>
    </div>
  );
}
