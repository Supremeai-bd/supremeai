import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';

interface ChatMessage {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  timestamp: string;
}

interface Skill {
  name: string;
  version: string;
  description: string;
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
  const [skills, setSkills] = useState<Record<string, Skill>>({});
  const [saveStatus, setSaveStatus] = useState('');
  const [adminMessages, setAdminMessages] = useState<ChatMessage[]>([
    { id: '1', sender: 'ai', text: "ঈশ্বর, আমি আপনার আদেশের অপেক্ষায় আছি। সংবিধান আইনসমূহ ড্যাশবোর্ডের ডান পাশ থেকে রিয়েল-টাইমে পরিবর্তন করতে পারেন।", timestamp: 'Just now' }
  ]);
  const [adminInput, setAdminInput] = useState('');
  const [cloudStats, setCloudStats] = useState<CloudStats | null>(null);
  const [gcpHealth, setGcpHealth] = useState<GcpHealth | null>(null);
  const [queueStats, setQueueStats] = useState<any>(null);

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

      // Fetch Skills
      const skillsRes = await fetch(`${API_BASE}/skills`);
      if (skillsRes.ok) {
        const skillsData = await skillsRes.json();
        setSkills(skillsData);
      }

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

      // Fetch Firestore queue stats
      const queueRes = await fetch(`${API_BASE}/gcp/verification-queue/stats`);
      if (queueRes.ok) {
        const qData = await queueRes.json();
        setQueueStats(qData);
      }

    } catch (err) {
      console.error("Error fetching admin stats", err);
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

                {/* Queue Size Telemetry */}
                {queueStats && (
                  <div className="mb-6">
                    <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold">Telemetry Queue Queue</div>
                    <div className="bg-black/40 border border-slate-900 rounded-lg p-3 flex flex-col gap-2 text-xs font-mono">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Queue Status:</span>
                        <span className="text-emerald-400">ACTIVE</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Verification Pending:</span>
                        <span className="text-orange-400">{queueStats.pending_count || 0}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Installed Agent Skills */}
                <div className="mb-6">
                  <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold">Active Agent Tools</div>
                  <div className="flex flex-col gap-2 max-h-48 overflow-y-auto">
                    {Object.keys(skills).map(key => (
                      <div key={key} className="bg-white/[0.01] border border-slate-900 rounded p-2.5 text-xs">
                        <div className="font-semibold text-slate-200 flex justify-between font-mono">
                          <span>{skills[key].name}</span>
                          <span className="text-[#00f3ff] text-[10px]">v{skills[key].version}</span>
                        </div>
                        <div className="text-slate-400 text-[10px] mt-1 font-sans">{skills[key].description}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-auto p-3 bg-cyan-950/20 border border-cyan-900/30 rounded-lg flex items-center gap-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#00f3ff] animate-pulse"></span>
                  <span className="text-xs font-semibold text-slate-300 font-mono">Authorized Admin Session</span>
                </div>
              </div>

              {/* Main Split Console */}
              <div className="flex-1 flex flex-row min-w-0">
                
                {/* Left side: Orchestrator Test Terminal */}
                <div className="w-1/2 border-r border-[#00f3ff]/10 flex flex-col bg-[#05070a]/50">
                  <div className="h-10 border-b border-slate-800 bg-[#090b11] px-4 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200 tracking-wider uppercase font-mono">Orchestrator Sandbox</span>
                    <span className="text-[10px] text-slate-500 font-mono">EXECUTE TERMINAL</span>
                  </div>

                  <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
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
                  <div className="h-10 border-b border-slate-800 bg-[#090b11] px-4 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200 tracking-wider uppercase font-mono">Constitutional Rules Database</span>
                    <div className="flex items-center gap-3">
                      {saveStatus && <span className="text-[10px] text-slate-400 font-mono">{saveStatus}</span>}
                      <button 
                        onClick={handleSaveRules}
                        className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold px-3 py-1.5 rounded transition-colors font-mono uppercase"
                      >
                        Apply Laws
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
