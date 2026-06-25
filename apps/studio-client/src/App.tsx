import React, { useEffect, useState } from "react";
import { useStore } from "./store/useStore";

export const App: React.FC = () => {
  const { 
    isServerOnline, setServerStatus, streamLogs, 
    deployGate, fetchGateStatus, executeGateOverride 
  } = useStore();

  // Local UI UI states for Override Panel
  const [showOverridePanel, setShowOverridePanel] = useState(false);
  const [targetStatus, setTargetStatus] = useState("UNLOCKED");
  const [justification, setJustification] = useState("");
  const [adminSecret, setAdminSecret] = useState("");
  const [apiFeedback, setApiFeedback] = useState<string | null>(null);

  useEffect(() => {
    const API_BASE_URL = import.meta.env.VITE_API_BASE || "http://localhost:8000";
    const sseEndpoint = `${API_BASE_URL}/api/task/stream`;
    
    console.log("🔌 Initializing SupremeAI Unified Lifespan SSE Stream...");
    const eventSource = new EventSource(sseEndpoint);

    eventSource.onopen = () => {
      setServerStatus(true);
      // সার্ভার অনলাইন হওয়ার সাথে সাথে গেটকিপার ডাটা সিঙ্ক
      fetchGateStatus();
    };

    eventSource.onerror = () => {
      console.error("🔴 [SYSTEM CRITICAL] SSE Stream severed. SupremeAI Server is OFFLINE.");
      setServerStatus(false);
    };

    return () => {
      eventSource.close();
    };
  }, [setServerStatus, fetchGateStatus]);

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiFeedback(null);
    const result = await executeGateOverride(targetStatus, justification, adminSecret);
    setApiFeedback(result.message);
    if (result.success) {
      setJustification("");
      setAdminSecret("");
      setTimeout(() => setShowOverridePanel(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 relative selection:bg-cyan-500 selection:text-slate-950">
      
      {/* ── HEADER & UNIFIED LIFESPAN BADGES ──────────────────────── */}
      <header className="flex justify-between items-center border-b border-slate-900 pb-4">
        <div>
          <h1 className="text-2xl font-black bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-500 bg-clip-text text-transparent tracking-tight">
            SupremeAI Studio Console 2.0
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-0.5">Autonomic & Hardened Production Core</p>
        </div>

        <div className="flex items-center gap-3">
          {/* 🛡️ Autonomous CI/CD Gate Monitor Widget */}
          <div 
            onClick={() => fetchGateStatus()}
            className="flex items-center gap-2 bg-slate-900/90 border border-slate-800 hover:border-slate-700 px-3 py-1.5 rounded-lg shadow-md backdrop-blur-md cursor-pointer transition-all"
          >
            <span className={`h-2 w-2 rounded-full ${deployGate?.status === "UNLOCKED" ? "bg-emerald-500" : "bg-rose-500 animate-ping"}`} />
            <span className="text-xs font-mono font-bold text-slate-300">
              GATE: {deployGate?.status || "SYNCING..."}
            </span>
          </div>

          {/* Core Health Badge */}
          <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-lg shadow-md backdrop-blur-md">
            <span className={`h-2 w-2 rounded-full ${isServerOnline ? "bg-cyan-500 animate-pulse" : "bg-rose-600"}`} />
            <span className="text-xs font-mono font-bold text-slate-300">
              CORE: {isServerOnline ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
        </div>
      </header>

      {/* ── MAIN ORCHESTRATION GRAPH & WORKSPACE ──────────────────── */}
      <main className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left/Middle Column: Infrastructure Insight */}
        <div className="lg:col-span-2 space-y-6">
          <section className="p-6 bg-slate-900/40 border border-slate-900 rounded-2xl backdrop-blur-sm">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 font-mono">// Deploy Gate Telemetry</h3>
            <div className="mt-4 p-4 bg-slate-950/80 border border-slate-900 rounded-xl">
              <p className="text-xs font-mono text-slate-400">
                <span className="text-indigo-400">Current Status:</span>{" "}
                <span className={deployGate?.status === "UNLOCKED" ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                  {deployGate?.status || "FETCHING FROM CLOUD..."}
                </span>
              </p>
              <p className="text-xs font-mono text-slate-400 mt-2">
                <span className="text-indigo-400">Gate Justification:</span> {deployGate?.reason || "Verifying structural artifacts..."}
              </p>
            </div>
            
            <button 
              onClick={() => setShowOverridePanel(!showOverridePanel)}
              className="mt-4 text-xs font-mono font-bold bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-indigo-500/50 px-4 py-2 rounded-lg text-indigo-400 transition-all"
            >
              🔱 Trigger God-Mode Gate Override
            </button>
          </section>

          {/* Live Action Logs Dashboard */}
          <section className="p-6 bg-slate-900/20 border border-slate-900 rounded-2xl">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 font-mono">// Active Infrastructure Streaming Stack</h3>
            <div className="mt-4 p-4 bg-slate-950 border border-slate-900 rounded-xl font-mono text-xs h-48 overflow-y-auto shadow-inner">
              {streamLogs?.length === 0 ? (
                <p className="text-slate-600">// Standing by for live streaming events from Cloud Run...</p>
              ) : (
                streamLogs?.map((log: string, idx: number) => <p key={idx} className="text-cyan-400/90 mt-1">→ {log}</p>)
              )}
            </div>
          </section>
        </div>

        {/* Right Column: Widgets & Overrides */}
        <div className="space-y-6">
          <EvolutionForgeWidget />
          
          {showOverridePanel && (
            <div className="p-6 bg-slate-900 border border-indigo-900/50 rounded-2xl shadow-2xl shadow-indigo-950/20 animate-fade-in">
              <h3 className="text-sm font-black uppercase tracking-wider text-indigo-400 font-mono">🔱 God-Mode Override Override</h3>
              <p className="text-xs text-slate-400 mt-1">Force-flip the state of the CI/CD deployment locks manually.</p>
              
              <form onSubmit={handleOverrideSubmit} className="mt-4 space-y-4">
                <div>
                  <label htmlFor="targetState" className="block text-[10px] uppercase font-mono tracking-widest text-slate-500">Target State</label>
                  <select 
                    id="targetState"
                    value={targetStatus} 
                    onChange={(e) => setTargetStatus(e.target.value)}
                    className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs font-mono text-slate-200 focus:border-indigo-500 outline-none"
                  >
                    <option value="UNLOCKED">🟢 FORCE UNLOCKED (Approve Pipeline)</option>
                    <option value="LOCKED">🔴 FORCE LOCKED (Kill Switch Pipeline)</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="overrideJustification" className="block text-[10px] uppercase font-mono tracking-widest text-slate-500">
                    Architect Justification
                    <textarea 
                      id="overrideJustification"
                      value={justification}
                      onChange={(e) => setJustification(e.target.value)}
                      placeholder="Minimum 10 characters required..."
                      required
                      rows={3}
                      className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs font-mono text-slate-200 focus:border-indigo-500 outline-none resize-none"
                    />
                  </label>
                </div>

                <div>
                  <label htmlFor="adminSecret" className="block text-[10px] uppercase font-mono tracking-widest text-slate-500">
                    Master Secret Vault Token
                    <input 
                      id="adminSecret"
                      type="password"
                      value={adminSecret}
                      onChange={(e) => setAdminSecret(e.target.value)}
                      placeholder="Enter secret key..."
                      required
                      className="w-full mt-1 bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs font-mono text-slate-200 focus:border-indigo-500 outline-none"
                    />
                  </label>
                </div>

                <button 
                  type="submit" 
                  className="w-full bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 font-mono font-bold text-xs py-2 px-4 rounded-lg shadow-md transition-all"
                >
                  Execute Global Override Commit
                </button>

                {apiFeedback && (
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-center">
                    <p className="text-[11px] font-mono text-cyan-400">{apiFeedback}</p>
                  </div>
                )}
              </form>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

// --- Evolution Forge Component ---
export const EvolutionForgeWidget: React.FC = () => {
  const { isForging, forgeFeedback, forgeSuccessCode, forgeNewSkill } = useStore();
  const [skillName, setSkillName] = useState("");
  const [userDemand, setUserDemand] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!skillName || !userDemand) return;
    
    // CamelCase ফরম্যাটিং এনসিওর করার জন্য বেসিক রেজেক্স ক্লিনিং
    const formattedName = skillName.replace(/[^a-zA-Z0-9]/g, "");
    forgeNewSkill(formattedName, userDemand);
  };

  return (
    <section className="p-6 bg-slate-900/40 border border-slate-900 rounded-2xl backdrop-blur-sm mt-6 lg:mt-0">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">🔥</span>
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-cyan-400 font-mono">// AI Evolution Forge</h3>
          <p className="text-[11px] text-slate-500 font-mono">Synthesize and deploy dynamic standalone tools on-the-fly</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-[10px] uppercase font-mono tracking-widest text-slate-400">Skill Class Name</label>
          <input 
            type="text"
            value={skillName}
            onChange={(e) => setSkillName(e.target.value)}
            placeholder="e.g., TwitterMarketingAgent"
            required
            disabled={isForging}
            className="w-full mt-1 bg-slate-950 border border-slate-800 focus:border-cyan-500 rounded-lg p-2 text-xs font-mono text-slate-200 outline-none transition-all"
          />
        </div>

        <div>
          <label className="block text-[10px] uppercase font-mono tracking-widest text-slate-400">Behavioral / Prompt Demand</label>
          <textarea 
            value={userDemand}
            onChange={(e) => setUserDemand(e.target.value)}
            placeholder="Describe the exact functionality, API integrations, and SEO prompt strategy required for this skill..."
            required
            rows={3}
            disabled={isForging}
            className="w-full mt-1 bg-slate-950 border border-slate-800 focus:border-cyan-500 rounded-lg p-2 text-xs font-mono text-slate-200 outline-none resize-none transition-all"
          />
        </div>

        <button 
          type="submit" 
          disabled={isForging}
          className={`w-full font-mono font-bold text-xs py-2.5 px-4 rounded-lg shadow-md transition-all ${
            isForging 
              ? "bg-slate-800 text-slate-500 cursor-not-allowed animate-pulse" 
              : "bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-slate-100"
          }`}
        >
          {isForging ? "⚡ FORGING & INJECTING HARDENED AST COMPONENT..." : "⚒️ Ignite Self-Evolution Sequence"}
        </button>
      </form>

      {/* 🔮 Feedback Notification Overlay */}
      {forgeFeedback && (
        <div className="mt-4 p-3 bg-slate-950 border border-slate-900 rounded-xl">
          <p className="text-xs font-mono text-slate-300 animate-fade-in text-center">
            {forgeFeedback}
          </p>
        </div>
      )}

      {/* 📜 Real-time Secure Code Viewer (If Compilation Passes) */}
      {forgeSuccessCode && (
        <div className="mt-4">
          <label className="block text-[10px] uppercase font-mono tracking-widest text-emerald-500 font-bold">✓ Sandbox Approved Compilation Output</label>
          <pre className="mt-1 p-3 bg-slate-950 border border-emerald-900/30 rounded-lg text-[10px] font-mono text-emerald-400/90 h-32 overflow-y-auto overflow-x-hidden shadow-inner">
            {forgeSuccessCode}
          </pre>
        </div>
      )}
    </section>
  );
};
