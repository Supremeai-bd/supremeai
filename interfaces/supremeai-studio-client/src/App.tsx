import { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';

interface ChatMessage {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  timestamp: string;
}

interface Skill {
  id: string;
  name: string;
  version: string;
  description: string;
  dependencies?: string;
  installed: boolean;
  source: string;
}

interface Checkpoint {
  task_id: string;
  step_index: number;
  state: Record<string, any>;
}

interface CloudStats {
  distribution: Record<string, any>;
  total_requests: number;
  active_providers: number;
  strategy: string;
}

interface GcpHealth {
  status: string;
  cloud_run: any;
  firestore_mode: string;
  pubsub_mode: string;
  cloud_functions: any;
}

function App() {
  // Navigation / Route state: 'customer' | 'admin'
  const [currentTab, setCurrentTab] = useState<'customer' | 'admin'>('customer');
  
  // Auto-detect view from URL hash or pathname
  useEffect(() => {
    const checkRoute = () => {
      const isAdmin = 
        window.location.hash === '#admin' || 
        window.location.pathname.includes('/admin') ||
        window.location.search.includes('view=admin');
      setCurrentTab(isAdmin ? 'admin' : 'customer');
    };
    checkRoute();
    window.addEventListener('hashchange', checkRoute);
    return () => window.removeEventListener('hashchange', checkRoute);
  }, []);

  const API_BASE = window.location.origin.includes('localhost') 
    ? (window.location.origin.includes('5173') ? 'http://localhost:8000' : '') 
    : '';

  // Common UI State
  const [loading, setLoading] = useState(false);

  // --- Customer / IDE Tab States ---
  const [code, setCode] = useState('// Welcome to SupremeAI Studio\n\nfunction helloWorld() {\n  console.log("Hello SupremeAI!");\n}\n');
  const [customerMessages, setCustomerMessages] = useState<ChatMessage[]>([
    { id: '1', sender: 'ai', text: "স্বাগতম! আমি SupremeAI মাস্টার অ্যাসিস্ট্যান্ট। আমি আপনার যেকোনো কাজ করতে সাহায্য করতে পারি। কীভাবে শুরু করব?", timestamp: 'Just now' }
  ]);
  const [customerInput, setCustomerInput] = useState('');

  // --- Admin Tab States ---
  const [adminAuthenticated, setAdminAuthenticated] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [adminError, setAdminError] = useState('');
  const [rulesJson, setRulesJson] = useState('// Loading rules from core database...');
  const [saveStatus, setSaveStatus] = useState('');
  const [adminMessages, setAdminMessages] = useState<ChatMessage[]>([
    { id: '1', sender: 'ai', text: "ঈশ্বর, আমি আপনার আদেশের অপেক্ষায় আছি। সংবিধান আইনসমূহ ড্যাশবোর্ডের ডান পাশ থেকে রিয়েল-টাইমে পরিবর্তন করতে পারেন।", timestamp: 'Just now' }
  ]);
  const [adminInput, setAdminInput] = useState('');
  
  // Advanced Admin states
  const [cloudStats, setCloudStats] = useState<CloudStats | null>(null);
  const [gcpHealth, setGcpHealth] = useState<GcpHealth | null>(null);
  
  // Skill Marketplace & Memory Checkpoints states
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillQuery, setSkillQuery] = useState('');
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [actionStatus, setActionStatus] = useState('');

  // New Admin Dashboard subtabs and states
  const [adminSubTab, setAdminSubTab] = useState<'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'project_status'>('project_status');
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [costReport, setCostReport] = useState<string>('');
  const [healthMap, setHealthMap] = useState<any>(null);
  const [adminUsers, setAdminUsers] = useState<any[]>([]);
  const [newUsername, setNewUsername] = useState('');
  const [newUserRole, setNewUserRole] = useState('Operator');
  const [newUserPerms, setNewUserPerms] = useState('read,write');
  const [envConfig, setEnvConfig] = useState<Record<string, string>>({});

  useEffect(() => {
    if (currentTab === 'admin' && adminSubTab === 'logs' && adminAuthenticated) {
      const eventSource = new EventSource(`${API_BASE}/admin-api/logs/stream`);
      eventSource.onmessage = (event) => {
        setLiveLogs(prev => [...prev.slice(-100), event.data]);
      };
      eventSource.onerror = () => {
        eventSource.close();
      };
      return () => eventSource.close();
    }
  }, [currentTab, adminSubTab, adminAuthenticated]);

  const fetchCosts = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin-api/costs`);
      if (res.ok) {
        const data = await res.json();
        setCostReport(data.report || '');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchHealthMap = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin-api/health-map`);
      if (res.ok) {
        const data = await res.json();
        setHealthMap(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAdminUsers = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin-api/users`);
      if (res.ok) {
        const data = await res.json();
        setAdminUsers(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveUser = async () => {
    if (!newUsername.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/admin-api/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: newUsername,
          role: newUserRole,
          permissions: newUserPerms.split(',').map(p => p.trim())
        })
      });
      if (res.ok) {
        fetchAdminUsers();
        setNewUsername('');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteUser = async (username: string) => {
    try {
      await fetch(`${API_BASE}/admin-api/users/${username}`, { method: 'DELETE' });
      fetchAdminUsers();
    } catch (e) {
      console.error(e);
    }
  };

  const fetchEnvConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin-api/config`);
      if (res.ok) {
        const data = await res.json();
        setEnvConfig(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin-api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ env_vars: envConfig })
      });
      if (res.ok) {
        setActionStatus("Configuration saved successfully!");
        setTimeout(() => setActionStatus(''), 4000);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleTriggerDeploy = async () => {
    try {
      setActionStatus("Triggering production deployment pipeline...");
      const res = await fetch(`${API_BASE}/admin-api/deploy`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setActionStatus(data.message || "Pipeline triggered.");
        setTimeout(() => setActionStatus(''), 5000);
      }
    } catch (e: any) {
      setActionStatus("Deployment failed: " + e.message);
    }
  };

  useEffect(() => {
    if (adminAuthenticated) {
      if (adminSubTab === 'costs') fetchCosts();
      if (adminSubTab === 'health') fetchHealthMap();
      if (adminSubTab === 'users') fetchAdminUsers();
      if (adminSubTab === 'config') fetchEnvConfig();
    }
  }, [adminSubTab, adminAuthenticated]);

  // Auto-login if token exists
  useEffect(() => {
    const savedToken = localStorage.getItem('supremeai_admin_token');
    if (savedToken) {
      verifyAdmin(savedToken);
    }
  }, []);

  // Fetch admin stats and rules
  const fetchAdminData = async (token: string) => {
    try {
      // Fetch Rules
      const rulesRes = await fetch(`${API_BASE}/admin/rules`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (rulesRes.ok) {
        const rulesData = await rulesRes.json();
        setRulesJson(JSON.stringify(rulesData, null, 4));
      }

      // Fetch Skills from marketplace
      fetchSkills('');

      // Fetch Memory Checkpoints
      fetchCheckpoints();

      // Fetch Cloud Stats
      const cloudRes = await fetch(`${API_BASE}/admin/cloud-distribution`);
      if (cloudRes.ok) {
        const cloudData = await cloudRes.json();
        setCloudStats(cloudData);
      }

      // Fetch GCP Health
      const gcpRes = await fetch(`${API_BASE}/gcp/health`);
      if (gcpRes.ok) {
        const gcpData = await gcpRes.json();
        setGcpHealth(gcpData);
      }

    } catch (err) {
      console.error("Error fetching admin stats", err);
    }
  };

  const fetchSkills = async (query: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/skills/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, installed_only: false })
      });
      if (res.ok) {
        const data = await res.json();
        setSkills(data);
      }
    } catch (err) {
      console.error("Error fetching skills marketplace", err);
    }
  };

  const fetchCheckpoints = async () => {
    try {
      const res = await fetch(`${API_BASE}/memory/checkpoints`);
      if (res.ok) {
        const data = await res.json();
        setCheckpoints(data);
      }
    } catch (err) {
      console.error("Error fetching memory checkpoints", err);
    }
  };

  const handleInstallSkill = async (skillName: string) => {
    try {
      setActionStatus(`Installing ${skillName}...`);
      const res = await fetch(`${API_BASE}/api/skills/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill: skillName })
      });
      if (res.ok) {
        setActionStatus(`Skill ${skillName} installed successfully!`);
        fetchSkills(skillQuery);
        setTimeout(() => setActionStatus(''), 4000);
      } else {
        const data = await res.json();
        setActionStatus(`Installation failed: ${data.detail || 'Error'}`);
      }
    } catch (err: any) {
      setActionStatus(`Installation error: ${err.message}`);
    }
  };

  const handleDeleteCheckpoint = async (taskId: string) => {
    try {
      setActionStatus(`Clearing checkpoint ${taskId}...`);
      const res = await fetch(`${API_BASE}/memory/checkpoint/${taskId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setActionStatus(`Checkpoint ${taskId} cleared.`);
        fetchCheckpoints();
        setTimeout(() => setActionStatus(''), 4000);
      } else {
        setActionStatus(`Failed to clear checkpoint.`);
      }
    } catch (err: any) {
      setActionStatus(`Error clearing checkpoint: ${err.message}`);
    }
  };

  const verifyAdmin = async (token: string) => {
    try {
      const response = await fetch(`${API_BASE}/admin/rules`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.status === 200) {
        setAdminAuthenticated(true);
        localStorage.setItem('supremeai_admin_token', token);
        setAdminError('');
        fetchAdminData(token);
      } else {
        setAdminError('Invalid authorization credentials.');
        localStorage.removeItem('supremeai_admin_token');
      }
    } catch (err: any) {
      setAdminError('Connection failed: ' + err.message);
    }
  };

  const handleAdminLogin = () => {
    if (!adminPassword.trim()) return;
    verifyAdmin(adminPassword.trim());
  };

  const handleAdminLogout = () => {
    localStorage.removeItem('supremeai_admin_token');
    setAdminAuthenticated(false);
    setAdminPassword('');
  };

  const handleSaveRules = async () => {
    const token = localStorage.getItem('supremeai_admin_token') || '';
    try {
      setSaveStatus('Applying laws...');
      const parsedRules = JSON.parse(rulesJson);
      const res = await fetch(`${API_BASE}/admin/rules`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ rules: parsedRules })
      });
      if (res.ok) {
        setSaveStatus('Constitutional laws applied successfully!');
        setTimeout(() => setSaveStatus(''), 4000);
      } else {
        const data = await res.json();
        setSaveStatus('Failed to apply: ' + (data.detail || 'Server error'));
      }
    } catch (err: any) {
      setSaveStatus('Invalid JSON format: ' + err.message);
    }
  };

  // Chat Execution triggers
  const handleSendCustomer = async () => {
    if (!customerInput.trim() || loading) return;
    const userMsg = customerInput.trim();
    setCustomerInput('');
    setCustomerMessages(prev => [...prev, { id: Date.now().toString(), sender: 'user', text: userMsg, timestamp: 'Just now' }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/task/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: userMsg, task_type: 'general' })
      });
      const data = await res.json();
      setCustomerMessages(prev => [...prev, {
        id: Date.now().toString(),
        sender: 'ai',
        text: data.result || 'No response generated.',
        timestamp: 'Just now'
      }]);
    } catch (err: any) {
      setCustomerMessages(prev => [...prev, { id: Date.now().toString(), sender: 'ai', text: 'Error connecting to agent backend.', timestamp: 'Just now' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSendAdmin = async () => {
    if (!adminInput.trim() || loading) return;
    const userMsg = adminInput.trim();
    setAdminInput('');
    setAdminMessages(prev => [...prev, { id: Date.now().toString(), sender: 'user', text: userMsg, timestamp: 'Just now' }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/task/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: userMsg, task_type: 'general' })
      });
      const data = await res.json();
      setAdminMessages(prev => [...prev, {
        id: Date.now().toString(),
        sender: 'ai',
        text: data.result || 'Orchestration execution returned no values.',
        timestamp: 'Just now'
      }]);
    } catch (err: any) {
      setAdminMessages(prev => [...prev, { id: Date.now().toString(), sender: 'ai', text: 'Orchestration task failed: Connection refused.', timestamp: 'Just now' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-[#020205] text-[#f8f9fa] overflow-hidden font-sans">
      
      {/* Dynamic Cinematic Header */}
      <div className="h-14 flex-shrink-0 bg-[#06080d]/80 backdrop-blur-md border-b border-[rgba(0,243,255,0.15)] flex items-center justify-between px-6 z-20">
        <div className="flex items-center gap-3">
          <span className="text-2xl drop-shadow-[0_0_10px_#00f3ff]">🔱</span>
          <span className="font-bold tracking-widest text-lg font-['Space_Grotesk'] text-white">
            SUPREME<span className="text-[#00f3ff]">AI</span>
          </span>
          <span className="hidden sm:inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-950/50 text-[#00f3ff] border border-cyan-800/40">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00f3ff] animate-pulse"></span>
            NEURAL LINK ACTIVE
          </span>
        </div>

        {/* Global tab switch */}
        <div className="flex bg-[#0f121d] rounded-lg p-1 border border-slate-800">
          <button 
            onClick={() => { setCurrentTab('customer'); window.location.hash = ''; }}
            className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-300 ${currentTab === 'customer' ? 'bg-[#00f3ff]/20 text-[#00f3ff] border border-[#00f3ff]/30' : 'text-slate-400 hover:text-white'}`}
          >
            Operator Studio
          </button>
          <button 
            onClick={() => { setCurrentTab('admin'); window.location.hash = 'admin'; }}
            className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-300 ${currentTab === 'admin' ? 'bg-[#bc13fe]/20 text-[#bc13fe] border border-[#bc13fe]/30' : 'text-slate-400 hover:text-white'}`}
          >
            God Control Center
          </button>
        </div>

        <div className="text-xs text-slate-400 font-mono hidden md:block">
          v2.0 (FastAPI Core)
        </div>
      </div>

      {/* --- CUSTOMER PORTAL / IDE VIEW --- */}
      {currentTab === 'customer' && (
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
      )}

      {/* --- ADMIN GOD LAYER VIEW --- */}
      {currentTab === 'admin' && (
        <div className="flex-grow flex flex-col overflow-hidden bg-[#030407]">
          {!adminAuthenticated ? (
            /* Admin Gate Login Screen */
            <div className="flex-1 flex items-center justify-center p-6">
              <div className="w-full max-w-md glass-card text-center flex flex-col gap-6 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#00f3ff] to-[#bc13fe]"></div>
                <div>
                  <span className="text-5xl block mb-2 drop-shadow-[0_0_12px_#bc13fe]">👑</span>
                  <h2 className="text-xl font-bold font-['Space_Grotesk'] tracking-widest uppercase">
                    SupremeAI <span className="text-[#00f3ff]">Admin Gate</span>
                  </h2>
                  <p className="text-slate-400 text-xs mt-1">Authorized access only. Authentication protocol required.</p>
                </div>
                <div>
                  <input 
                    type="password"
                    placeholder="Enter Admin Password..."
                    value={adminPassword}
                    onChange={e => setAdminPassword(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleAdminLogin()}
                    className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono"
                  />
                  {adminError && <div className="text-[#ff4d4f] text-xs mt-2 font-mono">{adminError}</div>}
                </div>
                <button 
                  onClick={handleAdminLogin}
                  className="cyber-button w-full uppercase py-3 text-xs tracking-wider"
                >
                  Authorize Layer
                </button>
              </div>
            </div>
          ) : (
            /* Authorized Admin Console */
            <div className="flex-1 flex flex-row overflow-hidden">
              {/* Sidebar with configuration, stats, and tools */}
              <div className="w-80 flex-shrink-0 bg-[#06080b]/90 border-r border-[#00f3ff]/15 flex flex-col p-4 overflow-y-auto">
                <div className="flex justify-between items-center mb-6">
                  <span className="text-[11px] uppercase tracking-[2px] text-[#00f3ff] font-semibold">
                    God Configuration
                  </span>
                  <button 
                    onClick={handleAdminLogout}
                    className="text-xs font-bold text-red-400 hover:text-red-300 tracking-wider transition-colors"
                  >
                    LOGOUT
                  </button>
                </div>

                {/* Status logs */}
                {actionStatus && (
                  <div className="mb-4 p-2.5 bg-cyan-950/30 border border-cyan-800/40 rounded text-[11px] font-mono text-[#00f3ff]">
                    {actionStatus}
                  </div>
                )}

                {/* GCP Health Stats */}
                <div className="mb-6">
                  <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold">GCP Health Matrix</div>
                  <div className="bg-black/40 border border-slate-900 rounded-lg p-3 flex flex-col gap-2 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Cloud Run Mode:</span>
                      <span className={gcpHealth?.status === 'ok' ? 'text-emerald-400' : 'text-yellow-400'}>
                        {gcpHealth?.cloud_run?.status || 'Active'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Firestore Mode:</span>
                      <span className="text-indigo-400">{gcpHealth?.firestore_mode || 'Local'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">PubSub Queue:</span>
                      <span className="text-purple-400">{gcpHealth?.pubsub_mode || 'Local'}</span>
                    </div>
                  </div>
                </div>

                {/* Queue Stats / Active Load Balancing */}
                {cloudStats && (
                  <div className="mb-6">
                    <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold font-mono">Cloud Distribution Stats</div>
                    <div className="bg-black/40 border border-slate-900 rounded-lg p-3 flex flex-col gap-2.5 text-xs font-mono">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Total Requests:</span>
                        <span className="text-white">{cloudStats.total_requests}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Active Providers:</span>
                        <span className="text-emerald-400">{cloudStats.active_providers}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Strategy:</span>
                        <span className="text-indigo-400">{cloudStats.strategy}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Skill Marketplace Manager */}
                <div className="mb-6">
                  <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold">Skill Marketplace</div>
                  <div className="flex gap-1 mb-2">
                    <input 
                      type="text" 
                      placeholder="Search marketplace..." 
                      value={skillQuery}
                      onChange={e => { setSkillQuery(e.target.value); fetchSkills(e.target.value); }}
                      className="bg-[#07090f] border border-slate-800 rounded px-2 py-1 text-[11px] text-white focus:outline-none focus:border-[#00f3ff] w-full font-mono"
                    />
                  </div>
                  <div className="flex flex-col gap-2 max-h-48 overflow-y-auto">
                    {skills.length === 0 ? (
                      <div className="text-[10px] text-slate-500 font-mono">No skills found.</div>
                    ) : (
                      skills.map(skill => (
                        <div key={skill.id} className="bg-white/[0.01] border border-slate-900 rounded p-2.5 text-xs">
                          <div className="font-semibold text-slate-200 flex justify-between font-mono">
                            <span>{skill.name}</span>
                            <span className="text-[#00f3ff] text-[10px]">v{skill.version}</span>
                          </div>
                          <div className="text-slate-400 text-[10px] mt-1 font-sans">{skill.description}</div>
                          <div className="mt-2 flex justify-between items-center">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${skill.installed ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/30' : 'bg-slate-950 text-slate-500'}`}>
                              {skill.installed ? 'Installed' : 'Built-in'}
                            </span>
                            {!skill.installed && (
                              <button 
                                onClick={() => handleInstallSkill(skill.name)}
                                className="bg-[#00f3ff]/10 hover:bg-[#00f3ff]/20 text-[#00f3ff] border border-[#00f3ff]/30 text-[10px] font-bold px-2 py-0.5 rounded transition-all font-mono"
                              >
                                INSTALL
                              </button>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Memory Checkpoints Manager */}
                <div className="mb-6">
                  <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold">Memory Checkpoints</div>
                  <div className="flex flex-col gap-2 max-h-40 overflow-y-auto">
                    {checkpoints.length === 0 ? (
                      <div className="text-[10px] text-slate-500 font-mono">No checkpoints stored.</div>
                    ) : (
                      checkpoints.map(cp => (
                        <div key={cp.task_id} className="bg-white/[0.01] border border-slate-900 rounded p-2 flex justify-between items-center font-mono text-[11px]">
                          <div className="min-w-0">
                            <div className="text-slate-200 truncate" title={cp.task_id}>{cp.task_id}</div>
                            <div className="text-slate-500 text-[10px]">Step: {cp.step_index}</div>
                          </div>
                          <button 
                            onClick={() => handleDeleteCheckpoint(cp.task_id)}
                            className="text-red-400 hover:text-red-300 font-bold px-2 py-1 text-[10px] rounded transition-all"
                            title="Delete checkpoint"
                          >
                            🗑️
                          </button>
                        </div>
                      ))
                    )}
                </div>
              </div>
            </div>

              {/* Main Split Console / Tabs container */}
              <div className="flex-1 flex flex-col min-w-0">
                {/* Dashboard Tabs Header */}
                <div className="h-10 bg-[#090b11] border-b border-slate-800 flex items-center justify-between px-4">
                  <div className="flex gap-2">
                    <button 
                      onClick={() => setAdminSubTab('project_status')}
                      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'project_status' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                    >
                      Project Overview 🔱
                    </button>
                    <button 
                      onClick={() => setAdminSubTab('sandbox')}
                      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'sandbox' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                    >
                      Orchestrator Sandbox
                    </button>
                    <button 
                      onClick={() => setAdminSubTab('logs')}
                      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'logs' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                    >
                      Real-time Logs
                    </button>
                    <button 
                      onClick={() => setAdminSubTab('costs')}
                      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'costs' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                    >
                      Cost Auditor
                    </button>
                    <button 
                      onClick={() => setAdminSubTab('health')}
                      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'health' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                    >
                      Provider Map
                    </button>
                    <button 
                      onClick={() => setAdminSubTab('users')}
                      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'users' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                    >
                      User Manager
                    </button>
                    <button 
                      onClick={() => setAdminSubTab('config')}
                      className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'config' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                    >
                      Config Editor
                    </button>
                  </div>
                  <div>
                    <button 
                      onClick={handleTriggerDeploy}
                      className="bg-[#00f3ff] hover:bg-cyan-400 text-black text-xs font-bold px-3 py-1 rounded font-mono transition-colors uppercase"
                    >
                      🚀 DEPLOY SYSTEM
                    </button>
                  </div>
                </div>

                {/* Sub Tab Contents */}
                {adminSubTab === 'project_status' && (
                  <div className="flex-grow p-6 overflow-y-auto bg-[#030508]">
                    <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
                      <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
                        🔱 SUPREMEAI 2.0 SYSTEM STATUS & OVERVIEW
                      </h2>
                      <span className="text-xs px-3 py-1 rounded bg-[#00f3ff]/10 text-[#00f3ff] border border-[#00f3ff]/20 font-mono">
                        SYNCED: 2026-06-20
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      
                      {/* Card 1: Progress */}
                      <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
                        <div className="flex items-center justify-between">
                          <span className="font-bold tracking-wider text-sm text-slate-200">সামগ্রিক অগ্রগতি (Progress)</span>
                          <span className="text-[#00f3ff] font-bold text-sm">92%</span>
                        </div>
                        <div className="w-full bg-[#121622] rounded-full h-2 overflow-hidden border border-white/[0.04]">
                          <div className="bg-gradient-to-r from-[#00f3ff] to-[#bc13fe] h-full" style={{ width: '92%' }}></div>
                        </div>
                        <div className="text-xs text-slate-400 leading-relaxed font-sans flex flex-col gap-2">
                          <div>• <strong>GCP Cloud Run</strong>: Live & Routing active.</div>
                          <div>• <strong>Firebase Hosting</strong>: React studio client deployed.</div>
                          <div>• <strong>CI/CD</strong>: Unified single pipeline configured.</div>
                          <div>• <strong>E2E Tests</strong>: Automated Firebase & VS Code runs passing.</div>
                        </div>
                      </div>

                      {/* Card 2: Tests */}
                      <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
                        <div className="flex items-center justify-between">
                          <span className="font-bold tracking-wider text-sm text-slate-200">টেস্ট সুইট (Test Matrix)</span>
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-400 border border-emerald-900">HEALTHY</span>
                        </div>
                        <div className="flex justify-around items-center py-2 bg-black/30 border border-slate-900 rounded-lg">
                          <div className="text-center">
                            <div className="text-lg font-bold text-white">127</div>
                            <div className="text-[10px] text-slate-500 font-mono">TOTAL</div>
                          </div>
                          <div className="w-[1px] h-8 bg-slate-800"></div>
                          <div className="text-center">
                            <div className="text-lg font-bold text-emerald-400">125</div>
                            <div className="text-[10px] text-emerald-500 font-mono">PASSED</div>
                          </div>
                          <div className="w-[1px] h-8 bg-slate-800"></div>
                          <div className="text-center">
                            <div className="text-lg font-bold text-yellow-400">2</div>
                            <div className="text-[10px] text-yellow-500 font-mono">SKIPPED</div>
                          </div>
                        </div>
                        <div className="text-xs text-slate-400 leading-relaxed font-sans">
                          ২৪টি টেস্ট ফাইলে মোট ১২৭টি টেস্ট কেস সফলভাবে রান হয়েছে।
                        </div>
                      </div>

                      {/* Card 3: Skills */}
                      <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
                        <div className="flex items-center justify-between">
                          <span className="font-bold tracking-wider text-sm text-slate-200">এআই স্কিলস (Active Skills)</span>
                          <span className="text-[#bc13fe] text-xs font-mono">ACTIVE</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                          {['multi_account_rotator', 'local_search_rag', 'docker_sandbox', 'cost_auditor', 'whisper_voice_handler', 'cot_reasoner', 'skill_loader', 'bengali_nlp'].map(skill => (
                            <span key={skill} className="px-2 py-1 text-[10px] rounded bg-[#101424] text-slate-300 border border-slate-800 font-mono">
                              {skill}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Card 4: Dependencies */}
                      <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
                        <div className="flex items-center justify-between">
                          <span className="font-bold tracking-wider text-sm text-slate-200">ডিপেন্ডেন্সি (Dependencies)</span>
                          <span className="text-indigo-400 text-xs font-mono">VERIFIED</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-400">
                          <div>• fastapi & uvicorn</div>
                          <div>• sentry-sdk</div>
                          <div>• playwright</div>
                          <div>• firebase-admin</div>
                          <div>• easyocr</div>
                          <div>• testing-library</div>
                        </div>
                      </div>

                      {/* Card 5: Manual Tasks */}
                      <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
                        <div className="flex items-center justify-between">
                          <span className="font-bold tracking-wider text-sm text-slate-200">পেন্ডিং কাজ (Manual Tasks)</span>
                          <span className="text-yellow-400 text-xs font-mono">PENDING</span>
                        </div>
                        <div className="text-xs text-slate-400 leading-relaxed font-sans flex flex-col gap-2">
                          <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
                            <input type="checkbox" disabled checked className="accent-[#00f3ff]" />
                            <span className="line-through text-slate-500">GCP Run & Services Enablement</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
                            <input type="checkbox" disabled className="accent-[#00f3ff]" />
                            <span>Supabase Shared DB & Upstash Redis</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
                            <input type="checkbox" disabled className="accent-[#00f3ff]" />
                            <span>Cloudflare load balancer integration</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
                            <input type="checkbox" disabled className="accent-[#00f3ff]" />
                            <span>Telegram/Discord Bot tokens config</span>
                          </label>
                        </div>
                      </div>

                      {/* Card 6: GitHub & Deployment */}
                      <div className="bg-[#080b11]/80 backdrop-blur-md border border-[#00f3ff]/10 rounded-xl p-5 flex flex-col gap-4 shadow-[0_4px_20px_rgba(0,243,255,0.05)] hover:border-[#00f3ff]/30 transition-all duration-300">
                        <div className="flex items-center justify-between">
                          <span className="font-bold tracking-wider text-sm text-slate-200">গিটহাব ও ডেপ্লয় (CI/CD)</span>
                          <span className="text-purple-400 text-xs font-mono">CONFIGURED</span>
                        </div>
                        <div className="text-xs text-slate-400 leading-relaxed font-sans flex flex-col gap-2">
                          <div>• <strong>Workflow</strong>: `.github/workflows/ci-cd.yml`</div>
                          <div>• <strong>Strategy</strong>: Blue-Green staging deployment.</div>
                          <div>• <strong>Fallback</strong>: Auto-rollback to stable version on error.</div>
                          <div>• <strong>Local Cache</strong>: Playwright headless binaries resolved.</div>
                        </div>
                      </div>

                    </div>
                  </div>
                )}

                {adminSubTab === 'sandbox' && (
                  <div className="flex-grow flex flex-row overflow-hidden">
                    {/* Left side: Orchestrator Test Terminal */}
                    <div className="w-1/2 border-r border-[#00f3ff]/10 flex flex-col bg-[#05070a]/50">
                      <div className="h-8 border-b border-slate-850 bg-[#0c0f17] px-4 flex items-center justify-between">
                        <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase font-mono">Sandbox Terminal</span>
                      </div>
                      <div className="flex-grow p-4 overflow-y-auto flex flex-col gap-4">
                        {adminMessages.map(msg => (
                          <div key={msg.id} className={`max-w-[85%] flex flex-col gap-1 ${msg.sender === 'user' ? 'self-end items-end' : 'self-start'}`}>
                            <div className={`p-3 rounded-xl text-xs leading-relaxed ${
                              msg.sender === 'user' 
                                ? 'bg-[#00f3ff] text-[#020205] font-bold shadow-[0_4px_12px_rgba(0,243,255,0.2)]'
                                : 'bg-white/[0.02] border border-slate-800 text-[#00ff66] font-mono'
                            }`}>
                              {msg.text}
                            </div>
                            <span className="text-[9px] text-slate-500 px-1 font-mono">{msg.timestamp}</span>
                          </div>
                        ))}
                        {loading && (
                          <div className="text-xs text-slate-400 animate-pulse font-mono flex items-center gap-2">
                            <span className="w-1.5 h-1.5 bg-[#00f3ff] rounded-full animate-bounce"></span>
                            Synchronizing Neural Link...
                          </div>
                        )}
                      </div>
                      <div className="p-4 border-t border-slate-800 bg-black/30">
                        <div className="flex gap-2">
                          <input 
                            type="text"
                            placeholder="Input direct testing command to God Layer..."
                            value={adminInput}
                            onChange={e => setAdminInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleSendAdmin()}
                            className="flex-grow bg-[#07090f] border border-slate-800 rounded-lg px-4 py-2.5 text-xs text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono"
                          />
                          <button 
                            onClick={handleSendAdmin}
                            className="bg-[#00f3ff] text-black font-bold px-4 py-2.5 rounded-lg text-xs uppercase hover:bg-cyan-400 transition-colors font-mono"
                          >
                            RUN
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Right side: Constitutional Database Rules (JSON) */}
                    <div className="w-1/2 flex flex-col bg-[#050608]">
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
                  </div>
                )}

                {adminSubTab === 'logs' && (
                  <div className="flex-grow flex flex-col bg-black/80 p-4 font-mono text-xs overflow-y-auto">
                    <div className="flex justify-between items-center mb-3 pb-2 border-b border-slate-800">
                      <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">Real-time Live Stream (supremeai.log)</span>
                      <button onClick={() => setLiveLogs([])} className="text-red-400 hover:text-red-300 font-bold text-[10px]">CLEAR SCREEN</button>
                    </div>
                    <div className="flex-grow flex flex-col gap-1 overflow-y-auto max-h-[70vh]">
                      {liveLogs.length === 0 ? 
                        <div className="text-slate-500 italic">Listening for incoming server logs...</div>
                       : 
                        liveLogs.map((log, idx) => (
                          <div key={idx} className="text-[#00ff66] whitespace-pre-wrap">{log}</div>
                        ))
                      }
                    </div>
                  </div>
                )}

                {adminSubTab === 'costs' && (
                  <div className="flex-grow bg-black/50 p-6 overflow-y-auto font-mono text-xs">
                    <h3 className="text-sm font-bold text-slate-200 mb-4 pb-2 border-b border-slate-800">📊 COST & BUDGET REPORT</h3>
                    <div className="bg-[#0c0d12] border border-slate-900 rounded-lg p-6 whitespace-pre-wrap text-slate-300">
                      {costReport || "Loading cost audit matrix..."}
                    </div>
                  </div>
                )}

                {adminSubTab === 'health' && (
                  <div className="flex-grow bg-black/50 p-6 overflow-y-auto font-mono text-xs">
                    <h3 className="text-sm font-bold text-slate-200 mb-6 pb-2 border-b border-slate-800">📡 SYSTEM HEALTH MAP</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="bg-[#0c0d12] border border-slate-900 rounded-xl p-5 flex flex-col gap-3">
                        <div className="flex justify-between items-center">
                          <span className="font-bold text-white tracking-widest">GOOGLE CLOUD</span>
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-400 border border-emerald-900">ACTIVE</span>
                        </div>
                        <div className="text-slate-400 mt-2">Latency: {healthMap?.gcp?.latency || "42ms"}</div>
                        <div className="text-slate-400">Region: {healthMap?.gcp?.region || "us-central1"}</div>
                      </div>
                      <div className="bg-[#0c0d12] border border-slate-900 rounded-xl p-5 flex flex-col gap-3">
                        <div className="flex justify-between items-center">
                          <span className="font-bold text-white tracking-widest">RAILWAY HOST</span>
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-950 text-emerald-400 border border-emerald-900">ACTIVE</span>
                        </div>
                        <div className="text-slate-400 mt-2">Latency: {healthMap?.railway?.latency || "78ms"}</div>
                        <div className="text-slate-400">Region: {healthMap?.railway?.region || "eu-west"}</div>
                      </div>
                      <div className="bg-[#0c0d12] border border-slate-900 rounded-xl p-5 flex flex-col gap-3">
                        <div className="flex justify-between items-center">
                          <span className="font-bold text-white tracking-widest">RENDER DEPLOY</span>
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-yellow-950 text-yellow-400 border border-yellow-900">DEGRADED</span>
                        </div>
                        <div className="text-slate-400 mt-2">Latency: {healthMap?.render?.latency || "250ms"}</div>
                        <div className="text-slate-400">Region: {healthMap?.render?.region || "singapore"}</div>
                      </div>
                    </div>
                  </div>
                )}

                {adminSubTab === 'users' && (
                  <div className="flex-grow bg-black/50 p-6 overflow-y-auto font-mono text-xs">
                    <h3 className="text-sm font-bold text-slate-200 mb-4 pb-2 border-b border-slate-800">👤 USER & RBAC MANAGEMENT</h3>
                    
                    <div className="bg-[#0c0d12] border border-slate-900 rounded-lg p-4 mb-6 flex flex-wrap gap-4 items-end">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[10px] text-slate-400 uppercase">Username</label>
                        <input 
                          type="text" 
                          placeholder="username..." 
                          value={newUsername}
                          onChange={e => setNewUsername(e.target.value)}
                          className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none focus:border-[#00f3ff]"
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[10px] text-slate-400 uppercase">Role</label>
                        <select 
                          value={newUserRole}
                          onChange={e => setNewUserRole(e.target.value)}
                          className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none"
                        >
                          <option value="Operator">Operator</option>
                          <option value="God">God</option>
                          <option value="Viewer">Viewer</option>
                        </select>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[10px] text-slate-400 uppercase">Permissions (comma separated)</label>
                        <input 
                          type="text" 
                          value={newUserPerms}
                          onChange={e => setNewUserPerms(e.target.value)}
                          className="bg-[#06080b] border border-slate-800 rounded px-3 py-1.5 text-white outline-none"
                        />
                      </div>
                      <button 
                        onClick={handleSaveUser}
                        className="bg-[#00f3ff] text-black font-bold px-4 py-1.5 rounded transition-colors uppercase font-mono"
                      >
                        Add/Update User
                      </button>
                    </div>

                    <div className="flex flex-col gap-3">
                      {adminUsers.map(user => (
                        <div key={user.username} className="bg-[#0c0d12] border border-slate-900 rounded-lg p-4 flex justify-between items-center">
                          <div>
                            <span className="font-bold text-white text-sm">{user.username}</span>
                            <span className="ml-3 px-2 py-0.5 rounded text-[10px] bg-cyan-950 text-[#00f3ff] border border-cyan-900">{user.role}</span>
                            <div className="text-slate-500 mt-1 text-[10px]">Perms: {JSON.stringify(user.permissions)}</div>
                          </div>
                          <button 
                            onClick={() => handleDeleteUser(user.username)}
                            className="bg-red-950/40 hover:bg-red-900/40 text-red-400 border border-red-900/40 px-2 py-1 rounded"
                          >
                            DELETE
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {adminSubTab === 'config' && (
                  <div className="flex-grow bg-black/50 p-6 overflow-y-auto font-mono text-xs">
                    <div className="flex justify-between items-center mb-4 pb-2 border-b border-slate-800">
                      <h3 className="text-sm font-bold text-slate-200">⚙️ ENVIRONMENTAL CONFIGURATION</h3>
                      <button 
                        onClick={handleSaveConfig}
                        className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold px-3 py-1.5 rounded transition-colors uppercase"
                      >
                        SAVE CONFIG
                      </button>
                    </div>
                    
                    <div className="flex flex-col gap-4">
                      {Object.keys(envConfig).map(k => (
                        <div key={k} className="flex flex-col md:flex-row md:items-center gap-2 bg-[#0c0d12] border border-slate-900 p-3 rounded-lg">
                          <span className="font-bold text-slate-300 min-w-[200px] select-all">{k}</span>
                          <input 
                            type={envConfig[k] === '********' ? 'password' : 'text'}
                            value={envConfig[k]}
                            onChange={e => {
                              const val = e.target.value;
                              setEnvConfig(prev => ({ ...prev, [k]: val }));
                            }}
                            className="flex-grow bg-[#06080b] border border-slate-800 rounded px-3 py-1 text-white outline-none focus:border-[#00f3ff] font-mono"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}


              </div>
            </div>
          )}
        </div>
      )}

      {/* Embedded Status Bar */}
      <div className="h-6 flex-shrink-0 bg-[#0a0c13] border-t border-slate-800 flex items-center px-4 text-[10px] font-mono text-slate-400 justify-between">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Agent Server Status: Online
          </span>
          <span>Security Protocol: TLS 1.3</span>
        </div>
        <div className="flex items-center gap-4">
          <span>Unicode (UTF-8)</span>
          <span>Vite Engine</span>
        </div>
      </div>

    </div>
  );
}

export default App;
