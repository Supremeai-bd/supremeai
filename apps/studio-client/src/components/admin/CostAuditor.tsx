import { useState } from 'react';

interface CostAuditorProps {
  costReport: string;
}

export function CostAuditor({ costReport }: CostAuditorProps) {
  const [limit, setLimit] = useState(150.00);
  const spent = 42.67;
  const percentage = Math.min((spent / limit) * 100, 100);

  const providerCosts = [
    { name: "Google Gemini", spent: 18.24, quota: 50.00, color: "from-[#1a73e8] to-[#8ab4f8]" },
    { name: "OpenRouter (DeepSeek)", spent: 12.80, quota: 40.00, color: "from-[#ff6b6b] to-[#ff8787]" },
    { name: "Hugging Face Hub", spent: 6.45, quota: 30.00, color: "from-[#ffd43b] to-[#ffe066]" },
    { name: "Groq (Llama 3)", spent: 5.18, quota: 30.00, color: "from-[#20c997] to-[#38d9a9]" },
  ];

  const recentCharges = [
    { time: "2026-06-22 22:04:12", user: "admin", model: "gemini-1.5-pro", tokens: 14205, cost: 0.0125 },
    { time: "2026-06-22 22:01:45", user: "dev_team", model: "deepseek-coder", tokens: 8940, cost: 0.0078 },
    { time: "2026-06-22 21:55:30", user: "agent_orchestrator", model: "gpt-4o", tokens: 18320, cost: 0.0245 },
    { time: "2026-06-22 21:48:19", user: "user_491", model: "llama3-70b-groq", tokens: 3410, cost: 0.0034 },
  ];

  return (
    <div className="flex-grow bg-black/40 p-6 overflow-y-auto font-sans">
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-slate-800">
        <h3 className="text-sm font-bold text-slate-200 tracking-wider font-mono">📊 COST & BUDGET REPORT</h3>
        <span className="text-[10px] text-slate-400 font-mono bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">Billing Cycle: June 2026</span>
      </div>

      {/* Main Budget Card */}
      <div className="bg-gradient-to-br from-[#0c0d14] to-[#12131f] border border-slate-900 rounded-xl p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">Total Spent</span>
            <span className="text-3xl font-extrabold text-white mt-1 font-mono">${spent.toFixed(2)}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">Budget Cap</span>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-2xl font-bold text-slate-300 font-mono">${limit.toFixed(2)}</span>
              <button 
                onClick={() => setLimit(prev => prev + 50)} 
                className="text-[9px] font-bold bg-[#00f3ff]/10 hover:bg-[#00f3ff]/20 text-[#00f3ff] border border-[#00f3ff]/20 px-2 py-0.5 rounded transition-all font-mono"
              >
                INCREASE
              </button>
            </div>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider">Usage Percentage</span>
            <span className="text-2xl font-bold text-[#00ff66] mt-1 font-mono">{percentage.toFixed(1)}%</span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-slate-950 border border-slate-900 h-2.5 rounded-full overflow-hidden">
          <div 
            className="bg-gradient-to-r from-[#00f3ff] to-[#00ff66] h-full transition-all duration-500 shadow-[0_0_10px_rgba(0,243,255,0.3)]"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {/* Provider Quotas */}
      <h4 className="text-xs font-bold text-slate-400 mb-4 tracking-wider uppercase font-mono">Provider Quotas & Consumption</h4>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {providerCosts.map(prov => {
          const provPercent = Math.min((prov.spent / prov.quota) * 100, 100);
          return (
            <div key={prov.name} className="bg-[#090a0f] border border-slate-900/60 rounded-xl p-4 flex flex-col gap-3">
              <div className="flex justify-between items-center">
                <span className="font-bold text-xs text-white">{prov.name}</span>
                <span className="text-[10px] font-bold text-slate-400 font-mono">${prov.spent.toFixed(2)} / ${prov.quota.toFixed(0)}</span>
              </div>
              <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden">
                <div 
                  className={`bg-gradient-to-r ${prov.color} h-full`}
                  style={{ width: `${provPercent}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent Usage Logs */}
      <h4 className="text-xs font-bold text-slate-400 mb-4 tracking-wider uppercase font-mono">Recent Query Charges</h4>
      <div className="bg-[#090a0f] border border-slate-900/60 rounded-xl overflow-hidden mb-6">
        <table className="w-full text-left font-mono text-[10px] text-slate-300">
          <thead>
            <tr className="bg-slate-900/50 border-b border-slate-800 text-slate-400">
              <th className="p-3">Timestamp</th>
              <th className="p-3">User/System</th>
              <th className="p-3">Model</th>
              <th className="p-3">Tokens</th>
              <th className="p-3 text-right">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-900">
            {recentCharges.map((chg, idx) => (
              <tr key={idx} className="hover:bg-slate-800/10">
                <td className="p-3 text-slate-500">{chg.time}</td>
                <td className="p-3 font-bold text-slate-200">{chg.user}</td>
                <td className="p-3 text-cyan-400">{chg.model}</td>
                <td className="p-3">{chg.tokens.toLocaleString()}</td>
                <td className="p-3 text-right text-[#00ff66] font-bold">${chg.cost.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Raw Output Log */}
      <details className="mt-4">
        <summary className="text-[10px] text-slate-500 cursor-pointer font-mono select-none uppercase hover:text-slate-400">Show raw console output</summary>
        <pre className="bg-[#0c0d12] border border-slate-900 rounded-lg p-4 mt-2 text-slate-400 font-mono text-[10px] whitespace-pre-wrap leading-relaxed">
          {costReport || "No raw cost reports currently in buffer."}
        </pre>
      </details>
    </div>
  );
}
