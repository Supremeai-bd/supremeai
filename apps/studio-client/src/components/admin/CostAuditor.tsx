interface CostAuditorProps {
  costReport: string;
}

export function CostAuditor({ costReport }: CostAuditorProps) {
  return (
    <div className="flex-grow bg-black/50 p-6 overflow-y-auto font-mono text-xs">
      <h3 className="text-sm font-bold text-slate-200 mb-4 pb-2 border-b border-slate-800">📊 COST & BUDGET REPORT</h3>
      <div className="bg-[#0c0d12] border border-slate-900 rounded-lg p-6 whitespace-pre-wrap text-slate-300">
        {costReport || "Loading cost audit matrix..."}
      </div>
    </div>
  );
}
