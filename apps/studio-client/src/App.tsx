import React, { useEffect, useState, useMemo } from "react";
import { useStore } from "./store/useStore";
import { useAdminStore } from "./store/adminStore";
import { AdminConsole } from "./components/admin/AdminConsole";

import { Cpu, Send } from 'lucide-react';
import ReactFlow, { Background, useNodesState, useEdgesState } from 'reactflow';
import 'reactflow/dist/style.css';
import './components/admin/AethelCoreStyles.css';
import AethelNode from './components/admin/AethelNode';

function AdminShell() {
  const {
    adminAuthenticated,
    adminPassword,
    setAdminPassword,
    adminError,
    handleAdminLogin,
    otpRequired,
    adminOtp,
    setAdminOtp,
    handleAdminLogout,
    actionStatus,
    setActionStatus,
  } = useAdminStore();

  const [adminEmail, setAdminEmail] = useState("admin@supremeai.dev");
  const [totpSetupRequired] = useState(false);
  const [totpSecret] = useState("JBSWY3DPEHPK3PXP");
  const [provisioningUri] = useState("");
  const [adminSubTab, setAdminSubTab] = useState<any>("command-center");
  const [skillQuery, setSkillQuery] = useState("");
  const [skillsList] = useState<any[]>([]);
  const [checkpointsList] = useState<any[]>([]);
  const [adminMessages, setAdminMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [adminInput, setAdminInput] = useState("");
  const [rulesJson, setRulesJson] = useState("{}");
  const [saveStatus, setSaveStatus] = useState("");
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [costReport, setCostReport] = useState("");
  const [healthMap, setHealthMap] = useState<any>({});
  const [newUsername, setNewUsername] = useState("");
  const [newUserRole, setNewUserRole] = useState("Operator");
  const [newUserPerms, setNewUserPerms] = useState("read,write");
  const [adminUsers, setAdminUsers] = useState<any[]>([]);
  const [envConfig, setEnvConfig] = useState<Record<string, string>>({});
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  useEffect(() => {
    if (!adminAuthenticated) return;

    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
    const headers = {
      "Authorization": `Bearer ${localStorage.getItem('supremeai_admin_token') || ''}`,
      "Content-Type": "application/json"
    };

    fetch(`${API_BASE}/admin-api/health-map`, { headers })
      .then(res => res.json())
      .then(data => setHealthMap(data))
      .catch(err => console.error("Error fetching health map:", err));

    fetch(`${API_BASE}/admin-api/costs`, { headers })
      .then(res => res.json())
      .then(data => setCostReport(data.report || ""))
      .catch(err => console.error("Error fetching cost report:", err));

    fetch(`${API_BASE}/admin-api/users`, { headers })
      .then(res => res.json())
      .then(data => setAdminUsers(data))
      .catch(err => console.error("Error fetching users:", err));

    setEnvConfig({
      "ENV": "local",
      "DEBUG": "true",
      "PORT": "8000",
      "GCP_REGION": "us-central1"
    });

  }, [adminAuthenticated]);

  const handleAdminOtpVerify = () => {
    handleAdminLogin();
  };

  const handleInstallSkill = (name: string) => {
    console.log("Install skill", name);
  };

  const handleDeleteCheckpoint = (taskId: string) => {
    console.log("Delete checkpoint", taskId);
  };

  const handleTriggerDeploy = () => {
    setActionStatus("TRIGGERING DEPLOY...");
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
    const headers = {
      "Authorization": `Bearer ${localStorage.getItem('supremeai_admin_token') || ''}`,
      "Content-Type": "application/json"
    };
    fetch(`${API_BASE}/admin-api/deploy`, { method: "POST", headers })
      .then(res => res.json())
      .then(() => {
        setActionStatus("DEPLOY TRIGGERED");
        setTimeout(() => setActionStatus(""), 2000);
      })
      .catch(() => {
        setActionStatus("DEPLOY FAILED");
        setTimeout(() => setActionStatus(""), 2000);
      });
  };

  const handleSendAdmin = () => {
    if (!adminInput.trim()) return;
    setAdminMessages(prev => [...prev, { id: crypto.randomUUID(), sender: 'user', text: adminInput, timestamp: new Date().toLocaleTimeString() }]);
    setAdminInput("");
    setLoading(true);
    setTimeout(() => {
      setAdminMessages(prev => [...prev, { id: crypto.randomUUID(), sender: 'bot', text: `Command processed: "${adminInput}". Status: SUCCESS.`, timestamp: new Date().toLocaleTimeString() }]);
      setLoading(false);
    }, 1000);
  };

  const handleSaveRules = () => {
    setSaveStatus("SAVING...");
    setTimeout(() => setSaveStatus("SAVED"), 1000);
  };

  const handleSaveUser = () => {
    if (!newUsername) return;
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
    const headers = {
      "Authorization": `Bearer ${localStorage.getItem('supremeai_admin_token') || ''}`,
      "Content-Type": "application/json"
    };
    fetch(`${API_BASE}/admin-api/users`, {
      method: "POST",
      headers,
      body: JSON.stringify({ username: newUsername, role: newUserRole, permissions: newUserPerms.split(",") })
    })
      .then(res => res.json())
      .then(() => {
        setAdminUsers(prev => [...prev, { username: newUsername, role: newUserRole, permissions: newUserPerms.split(",") }]);
        setNewUsername("");
      })
      .catch(err => console.error("Error creating user:", err));
  };

  const handleDeleteUser = (username: string) => {
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
    const headers = {
      "Authorization": `Bearer ${localStorage.getItem('supremeai_admin_token') || ''}`,
      "Content-Type": "application/json"
    };
    fetch(`${API_BASE}/admin-api/users/${username}`, { method: "DELETE", headers })
      .then(res => res.json())
      .then(() => {
        setAdminUsers(prev => prev.filter(u => u.username !== username));
      })
      .catch(err => console.error("Error deleting user:", err));
  };

  const handleSaveConfig = () => {
    console.log("Saving environment configs", envConfig);
  };

  return (
    <AdminConsole
      adminAuthenticated={adminAuthenticated}
      adminPassword={adminPassword}
      setAdminPassword={setAdminPassword}
      adminEmail={adminEmail}
      setAdminEmail={setAdminEmail}
      totpSetupRequired={totpSetupRequired}
      totpSecret={totpSecret}
      provisioningUri={provisioningUri}
      adminError={adminError}
      handleAdminLogin={handleAdminLogin}
      handleAdminOtpVerify={handleAdminOtpVerify}
      handleAdminLogout={handleAdminLogout}
      actionStatus={actionStatus}
      gcpHealth={null}
      cloudStats={null}
      skillQuery={skillQuery}
      setSkillQuery={setSkillQuery}
      skills={skillsList}
      handleInstallSkill={handleInstallSkill}
      checkpoints={checkpointsList}
      handleDeleteCheckpoint={handleDeleteCheckpoint}
      adminSubTab={adminSubTab}
      setAdminSubTab={setAdminSubTab}
      handleTriggerDeploy={handleTriggerDeploy}
      adminMessages={adminMessages}
      loading={loading}
      adminInput={adminInput}
      setAdminInput={setAdminInput}
      handleSendAdmin={handleSendAdmin}
      rulesJson={rulesJson}
      setRulesJson={setRulesJson}
      saveStatus={saveStatus}
      handleSaveRules={handleSaveRules}
      liveLogs={liveLogs}
      setLiveLogs={setLiveLogs}
      costReport={costReport}
      healthMap={healthMap}
      newUsername={newUsername}
      setNewUsername={setNewUsername}
      newUserRole={newUserRole}
      setNewUserRole={setNewUserRole}
      newUserPerms={newUserPerms}
      setNewUserPerms={setNewUserPerms}
      handleSaveUser={handleSaveUser}
      adminUsers={adminUsers}
      handleDeleteUser={handleDeleteUser}
      envConfig={envConfig}
      setEnvConfig={setEnvConfig}
      handleSaveConfig={handleSaveConfig}
      otpRequired={otpRequired}
      adminOtp={adminOtp}
      setAdminOtp={setAdminOtp}
      theme={theme}
      toggleTheme={toggleTheme}
    />
  );
}

export const App: React.FC = () => {
  const { 
    isServerOnline, setServerStatus, deployGate, fetchGateStatus 
  } = useStore();

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges] = useEdgesState([]);
  const [chatMessages, setChatMessages] = useState([
    { id: 1, sender: 'User', text: 'Initialize workspace analysis.' },
    { id: 2, sender: 'Aethel', text: 'Workspace active. Loaded 4 key skill connectors: Code Arch, Data Analyzer, Web Research, Custom Node.' }
  ]);
  const [chatInput, setChatInput] = useState('');

  // Custom node types for ReactFlow
  const nodeTypes = useMemo(() => ({ aethel: AethelNode }), []);

  const isAdminMode = () => {
    if (typeof window === "undefined") return false;
    return window.location.hostname.includes("admin") || window.location.pathname.startsWith("/admin");
  };

  const handleSendChat = () => {
    if (!chatInput.trim()) return;
    setChatMessages(prev => [
      ...prev,
      { id: Date.now(), sender: 'User', text: chatInput },
      { id: Date.now() + 1, sender: 'Aethel', text: `Analyzing request "${chatInput}"... Processing on central core.` }
    ]);
    setChatInput('');
  };

  useEffect(() => {
    const API_BASE_URL = import.meta.env.VITE_API_BASE || "http://localhost:8000";
    const sseEndpoint = `${API_BASE_URL}/api/task/stream`;
    
    console.log("🔌 Initializing SupremeAI Unified Lifespan SSE Stream...");
    const eventSource = new EventSource(sseEndpoint);

    eventSource.onopen = () => {
      setServerStatus(true);
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

  useEffect(() => {
    if (isAdminMode()) return;
    const initialNodes = [
      {
        id: 'central-orb',
        type: 'default',
        data: {
          label: (
            <div className="flex flex-col items-center justify-center p-2 text-center h-full w-full">
              <span className="font-bold text-[9px] tracking-widest text-[#00f3ff] uppercase mb-3">Central AI Core</span>
              <div className="central-orb-outer">
                <div className="central-orb-inner">
                  <div className="central-orb-core flex items-center justify-center bg-[#00f3ff] w-[45px] h-[45px] rounded-full shadow-[0_0_25px_#00f3ff]">
                    <Cpu size={22} className="text-slate-950" />
                  </div>
                </div>
              </div>
              <div className="mt-3 flex flex-col gap-0.5">
                <span className="text-[9px] text-[#00ff66] font-mono font-bold">Personal Hub</span>
                <span className="text-[8px] text-slate-500 font-mono">ACTIVE</span>
              </div>
            </div>
          )
        },
        position: { x: 250, y: 80 },
        className: 'border-none flex items-center justify-center bg-transparent',
        style: { width: 220, height: 280 }
      },
      {
        id: 'node-code-arch',
        type: 'aethel',
        data: { type: 'swarm', status: 'Nominal', label: 'Code Arch' },
        position: { x: 30, y: 70 }
      },
      {
        id: 'node-data-analyzer',
        type: 'aethel',
        data: { type: 'mesh', status: 'Nominal', label: 'Data Analyzer' },
        position: { x: 30, y: 220 }
      },
      {
        id: 'node-web-research',
        type: 'aethel',
        data: { type: 'gateway', status: 'Nominal', label: 'Web Research' },
        position: { x: 500, y: 70 }
      },
      {
        id: 'node-custom-skill',
        type: 'aethel',
        data: { type: 'evolution', status: 'Nominal', label: 'Custom Node' },
        position: { x: 500, y: 220 }
      }
    ];

    const initialEdges = [
      { id: 'e-code-central', source: 'node-code-arch', target: 'central-orb', animated: true, style: { stroke: '#00f3ff', strokeWidth: 1.5 } },
      { id: 'e-data-central', source: 'node-data-analyzer', target: 'central-orb', animated: true, style: { stroke: '#00ff66', strokeWidth: 1.5 } },
      { id: 'e-web-central', source: 'central-orb', target: 'node-web-research', animated: true, style: { stroke: '#00f3ff', strokeWidth: 1.5 } },
      { id: 'e-custom-central', source: 'central-orb', target: 'node-custom-skill', animated: true, style: { stroke: '#ffbd2e', strokeWidth: 1.5 } }
    ];

    setNodes(initialNodes);
    setEdges(initialEdges);
  }, []);

  if (isAdminMode()) {
    return <AdminShell />;
  }

  return (
    <div className="min-h-screen bg-[#030611] text-white scanline relative h-screen font-mono p-4 flex flex-col overflow-hidden">
      
      {/* ── TOP HUD HEADER BAR ────────────────────────────────────── */}
      <header className="flex justify-between items-center border-b border-[#00f3ff]/15 pb-2 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-[#00f3ff] animate-pulse">▲</span>
          <span className="text-xs font-bold tracking-widest text-[#00f3ff] uppercase">AETHEL WORKSPACE HUD | USER-01</span>
        </div>
        <div className="text-sm font-bold tracking-widest text-[#00f3ff] uppercase">
          AETHEL CENTRAL WORKSPACE
        </div>
        <div className="flex items-center gap-4 text-[10px] text-[#00f3ff] font-bold">
          <span>GATE: {deployGate?.status || "SYNCING..."}</span>
          <span className={isServerOnline ? 'text-[#00f3ff]' : 'text-rose-500'}>
            📶 CORE: {isServerOnline ? "ONLINE" : "OFFLINE"}
          </span>
        </div>
      </header>

      {/* ── MAIN WORKSPACE CONTENT ────────────────────────────────── */}
      <div className="flex-1 flex flex-row gap-4 overflow-hidden mb-4">
        
        {/* Core React Flow Workspace Canvas */}
        <div className="flex-1 bg-[#050917]/50 border border-[#00f3ff]/15 rounded-xl relative overflow-hidden flex flex-col">
          <div className="flex-1 w-full h-full relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              fitView
              zoomOnScroll={false}
              zoomOnDoubleClick={false}
              preventScrolling={true}
              panOnDrag={false}
              nodesDraggable={true}
            >
              <Background color="#00f3ff" gap={24} style={{ opacity: 0.03 }} />
            </ReactFlow>
          </div>

          {/* Floating Voice wave bar widget at bottom center of canvas */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-[340px] bg-[#060b1b]/90 border border-[#00f3ff]/25 rounded-lg p-2.5 shadow-[0_0_20px_rgba(0,243,255,0.15)] backdrop-blur-md z-20 flex flex-col items-center">
            <div className="flex justify-between w-full text-[8px] text-slate-400 font-bold mb-1">
              <span>VOICE INTERFACE</span>
              <span>ACTIVE</span>
            </div>

            {/* Glowing Waveform representation */}
            <div className="flex items-center justify-center h-6 my-1 w-full">
              <span className="waveform-bar" style={{ height: '6px' }} />
              <span className="waveform-bar pulse-delay-1" style={{ height: '12px' }} />
              <span className="waveform-bar pulse-delay-2" style={{ height: '18px' }} />
              <span className="waveform-bar pulse-delay-3" style={{ height: '10px' }} />
              <span className="waveform-bar pulse-delay-4" style={{ height: '22px' }} />
              <span className="waveform-bar pulse-delay-5" style={{ height: '8px' }} />
              <span className="waveform-bar pulse-delay-1" style={{ height: '14px' }} />
              <span className="waveform-bar pulse-delay-2" style={{ height: '5px' }} />
            </div>

            <div className="text-[8px] text-slate-500 font-bold mt-1 text-center w-full">
              <span className="text-[#00f3ff] animate-pulse">🎤 Speaking... Waveform active</span>
            </div>
          </div>
        </div>

        {/* Right Glassmorphic Chat Panel */}
        <div className="w-[300px] flex flex-col bg-[#050917]/60 border border-[#00f3ff]/15 rounded-xl backdrop-blur-md overflow-hidden">
          <div className="border-b border-[#00f3ff]/15 p-3 flex justify-between items-center bg-[#070d22]">
            <span className="text-xs font-black tracking-widest text-[#00f3ff] uppercase">AETHEL | CHAT CONSOLE</span>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {chatMessages.map(msg => (
              <div key={msg.id} className="text-[10px] leading-relaxed border-b border-cyan-900/10 pb-2">
                <span className={`font-bold tracking-wider mr-1 ${
                  msg.sender === 'User' ? 'text-slate-300' : 'text-[#00f3ff]'
                }`}>
                  {msg.sender}:
                </span>
                <span className="text-slate-300">{msg.text}</span>
              </div>
            ))}
          </div>

          <div className="p-3 border-t border-[#00f3ff]/15 bg-[#060b1c]/80 flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendChat()}
              placeholder="[Type message...]"
              className="flex-grow bg-[#030611] border border-cyan-500/20 focus:border-[#00f3ff]/60 rounded px-2.5 py-1.5 text-[10px] text-slate-100 outline-none placeholder:text-slate-600"
            />
            <button onClick={handleSendChat} className="bg-[#00f3ff]/20 hover:bg-[#00f3ff]/40 text-[#00f3ff] p-1.5 rounded transition-all">
              <Send size={12} />
            </button>
          </div>
        </div>

      </div>

      {/* ── BOTTOM HUD STATUS FOOTER ──────────────────────────────── */}
      <footer className="flex justify-between items-center border-t border-[#00f3ff]/15 pt-2 text-[8px] text-slate-500 font-bold uppercase tracking-wider">
        <span>AETHEL CENTRAL ORC — SYSTEM STATE OK</span>
        <span>SupremeAI 2.0 Web Client</span>
      </footer>

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
