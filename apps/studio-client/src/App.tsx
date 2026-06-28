import React, { useEffect, useState, useMemo } from "react";
import { useStore } from "./store/useStore";
import { useAdminStore } from "./store/adminStore";
import { AdminConsole } from "./components/admin/AdminConsole";
import { UserDashboard } from "./components/customer/UserDashboard";

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
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

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
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    { id: 1, sender: 'User', text: 'Initialize workspace analysis.', timestamp: new Date().toLocaleTimeString() },
    { id: 2, sender: 'Aethel', text: 'Workspace active. Loaded 4 key skill connectors: Code Arch, Data Analyzer, Web Research, Custom Node.', timestamp: new Date().toLocaleTimeString() }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  const nodeTypes = useMemo(() => ({ aethel: AethelNode }), []);

  const isAdminMode = () => {
    if (typeof window === "undefined") return false;
    return window.location.hostname.includes("admin") || window.location.pathname.startsWith("/admin");
  };

  const handleSendChat = () => {
    if (!chatInput.trim()) return;
    const now = new Date().toLocaleTimeString();
    setChatMessages(prev => [
      ...prev,
      { id: Date.now(), sender: 'User', text: chatInput, timestamp: now },
      { id: Date.now() + 1, sender: 'Aethel', text: `Analyzing request "${chatInput}"... Processing on central core.`, timestamp: now }
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
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

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

  const handleSendCustomer = () => {
    if (!chatInput.trim()) return;
    const now = new Date().toLocaleTimeString();
    setChatMessages(prev => [
      ...prev,
      { id: Date.now(), sender: 'User', text: chatInput, timestamp: now },
      { id: Date.now() + 1, sender: 'Aethel', text: `Analyzing request "${chatInput}"... Processing on central core.`, timestamp: now }
    ]);
    setChatInput('');
  };

  return (
    <UserDashboard
      customerMessages={chatMessages}
      customerInput={chatInput}
      setCustomerInput={setChatInput}
      loading={false}
      handleSendCustomer={handleSendCustomer}
      theme={theme}
      toggleTheme={toggleTheme}
      code="// Your code here"
      setCode={() => {}}
      isServerOnline={isServerOnline}
      deployGate={deployGate}
      user={null}
      projects={[]}
      chatHistory={chatMessages}
      widgets={[]}
    />
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

      {forgeFeedback && (
        <div className="mt-4 p-3 bg-slate-950 border border-slate-900 rounded-xl">
          <p className="text-xs font-mono text-slate-300 animate-fade-in text-center">
            {forgeFeedback}
          </p>
        </div>
      )}

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
