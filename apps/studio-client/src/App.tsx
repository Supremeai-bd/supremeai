import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { OperatorStudio } from './components/OperatorStudio';
import { AdminConsole } from './components/AdminConsole';
import type { ChatMessage, Skill, Checkpoint, CloudStats, GcpHealth } from './types';

function App() {
  // Navigation / Route state: 'customer' | 'admin'
  const [currentTab, setCurrentTab] = useState<'customer' | 'admin'>('customer');
  
  // Auto-detect view from URL hash, pathname or hostname
  useEffect(() => {
    const checkRoute = () => {
      const hostname = window.location.hostname;
      const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
      const isAdminDomain = hostname.includes('admin');
      
      if (isLocalhost) {
        const isAdmin = 
          window.location.hash === '#admin' || 
          window.location.pathname.includes('/admin') ||
          window.location.search.includes('view=admin');
        setCurrentTab(isAdmin ? 'admin' : 'customer');
      } else if (isAdminDomain) {
        setCurrentTab('admin');
      } else {
        setCurrentTab('customer');
        // If user tries to access admin routes on studio domain in production, redirect
        if (
          window.location.hash === '#admin' || 
          window.location.pathname.includes('/admin') ||
          window.location.search.includes('view=admin')
        ) {
          window.location.href = 'https://supremeai-admin.web.app';
        }
      }
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
  const [adminOtp, setAdminOtp] = useState('');
  const [otpRequired, setOtpRequired] = useState(false);
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

  useEffect(() => {
    if (adminAuthenticated) {
      fetchSkills(skillQuery);
    }
  }, [skillQuery, adminAuthenticated]);

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

  const handleAdminLogin = async () => {
    if (!adminPassword.trim()) return;
    setAdminError('');
    try {
      if (!otpRequired) {
        const res = await fetch(`${API_BASE}/api/admin/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: adminPassword.trim() })
        });
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'otp_required') {
            setOtpRequired(true);
          }
        } else {
          const data = await res.json();
          setAdminError(data.detail || 'Invalid password.');
        }
      } else {
        const res = await fetch(`${API_BASE}/api/admin/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: adminPassword.trim(), otp: adminOtp.trim() })
        });
        if (res.ok) {
          const data = await res.json();
          setAdminAuthenticated(true);
          localStorage.setItem('supremeai_admin_token', data.token);
          setAdminError('');
          setOtpRequired(false);
          setAdminOtp('');
          fetchAdminData(data.token);
        } else {
          const data = await res.json();
          setAdminError(data.detail || 'Invalid verification code.');
        }
      }
    } catch (err: any) {
      setAdminError('Connection failed: ' + err.message);
    }
  };

  const handleAdminLogout = () => {
    localStorage.removeItem('supremeai_admin_token');
    setAdminAuthenticated(false);
    setAdminPassword('');
    setOtpRequired(false);
    setAdminOtp('');
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
      
      <Header currentTab={currentTab} setCurrentTab={setCurrentTab} />

      {/* --- CUSTOMER PORTAL / IDE VIEW --- */}
      {currentTab === 'customer' && (
        <OperatorStudio 
          code={code}
          setCode={setCode}
          customerMessages={customerMessages}
          customerInput={customerInput}
          setCustomerInput={setCustomerInput}
          loading={loading}
          handleSendCustomer={handleSendCustomer}
        />
      )}

      {/* --- ADMIN GOD LAYER VIEW --- */}
      {currentTab === 'admin' && (
        <AdminConsole 
          adminAuthenticated={adminAuthenticated}
          adminPassword={adminPassword}
          setAdminPassword={setAdminPassword}
          adminError={adminError}
          handleAdminLogin={handleAdminLogin}
          handleAdminLogout={handleAdminLogout}
          actionStatus={actionStatus}
          gcpHealth={gcpHealth}
          cloudStats={cloudStats}
          skillQuery={skillQuery}
          setSkillQuery={setSkillQuery}
          skills={skills}
          handleInstallSkill={handleInstallSkill}
          checkpoints={checkpoints}
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
        />
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
