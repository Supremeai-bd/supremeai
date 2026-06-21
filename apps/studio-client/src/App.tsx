import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { OperatorStudio } from './components/OperatorStudio';
import { AdminConsole } from './components/AdminConsole';
import { useThemeStore } from './store/themeStore';
import type { ChatMessage, Skill, Checkpoint, CloudStats, GcpHealth, HealthMap, AdminUser } from './types';

function App() {
  // Navigation / Route state: 'customer' | 'admin'
  const [currentTab, setCurrentTab] = useState<'customer' | 'admin'>('customer');

  // Auto-detect view from URL hash, pathname or hostname
  useEffect(() => {
    const checkRoute = () => {
      const hostname = window.location.hostname;
      const isAdminDomain = hostname.includes('admin');

      if (isAdminDomain) {
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

    const API_BASE = import.meta.env.VITE_API_BASE || '';

    // Theme state from zustand store
    const { theme, toggleTheme } = useThemeStore();

    useEffect(() => {
      if (theme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }, [theme]);

    // Common UI State
    const [loading, setLoading] = useState(false);
    const [serverOnline, setServerOnline] = useState(true);

    useEffect(() => {
      const eventSource = new EventSource(`${API_BASE}/admin-api/logs/stream`);
      
      eventSource.onopen = () => {
        setServerOnline(true);
      };
      
      eventSource.onmessage = () => {
        setServerOnline(true);
      };
      
      eventSource.onerror = () => {
        setServerOnline(false);
      };
      
      return () => {
        eventSource.close();
      };
    }, [API_BASE]);

  // Session ID for context preservation
  const [sessionId] = useState(() => {
    let id = localStorage.getItem('supremeai_session_id');
    if (!id) {
      id = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : Math.random().toString(36).substring(2);
      localStorage.setItem('supremeai_session_id', id);
    }
    return id;
  });

  // --- Customer / IDE Tab States ---
  const [code, setCode] = useState('// Welcome to SupremeAI Studio\n\nfunction helloWorld() {\n  console.log("Hello SupremeAI!");\n}\n');
  const [customerMessages, setCustomerMessages] = useState<ChatMessage[]>([
    { id: '1', sender: 'ai', text: "স্বাগতম! আমি SupremeAI মাস্টার অ্যাসিস্ট্যান্ট। আমি আপনার যেকোনো কাজ করতে সাহায্য করতে পারি। কীভাবে শুরু করব?", timestamp: 'Just now' }
  ]);
  const [customerInput, setCustomerInput] = useState('');


  // --- Admin Tab States ---
  // Added by Agent Antigravity on 2026-06-21: Support email login and personalized TOTP secret setup
  const [adminEmail, setAdminEmail] = useState('');
  const [totpSetupRequired, setTotpSetupRequired] = useState(false);
  const [totpSecret, setTotpSecret] = useState('');
  const [provisioningUri, setProvisioningUri] = useState('');

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
  const [adminSubTab, setAdminSubTab] = useState<'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'command-center' | 'model-router' | 'skills' | 'memory' | 'cloud' | 'observability' | 'threats' | 'rules' | 'cicd' | 'github' | 'backups'>('command-center');
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [costReport, setCostReport] = useState<string>('');
  const [healthMap, setHealthMap] = useState<HealthMap | null>(null);
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
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

  // --- Agentic Security: Firebase Auth & Unique TOTP Login ---
  // Added by Agent Antigravity on 2026-06-21. Handles first-factor Firebase Email/Password sign-in
  // followed by dynamic TOTP registration or validation against unique keys.

  const handleAdminLogin = async () => {
    if (!adminEmail.trim() || !adminPassword.trim()) {
      setAdminError('Email and Password are required.');
      return;
    }
    setAdminError('');
    setLoading(true);
    try {
      const { getFirebaseAuth } = await import('./firebase');
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      const authInstance = await getFirebaseAuth();
      
      // Step 1: Firebase Authentication
      const userCredential = await signInWithEmailAndPassword(authInstance, adminEmail.trim(), adminPassword.trim());
      const idToken = await userCredential.user.getIdToken();
      
      // Step 2: Contact backend to verify admin role and TOTP status
      const res = await fetch(`${API_BASE}/api/admin/firebase-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: idToken })
      });
      
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Access Denied: Admin authorization failed.');
      }
      
      const data = await res.json();
      
      if (data.status === 'totp_setup_required') {
        // Request unique TOTP setup uri
        const setupRes = await fetch(`${API_BASE}/api/admin/firebase-totp-setup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_token: idToken })
        });
        const setupData = await setupRes.json();
        setTotpSecret(setupData.secret);
        setProvisioningUri(setupData.provisioning_uri);
        setTotpSetupRequired(true);
        setOtpRequired(true);
      } else if (data.status === 'totp_required') {
        setOtpRequired(true);
        setTotpSetupRequired(false);
      }
    } catch (err: any) {
      setAdminError(err.message || 'Authentication failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleAdminOtpVerify = async () => {
    if (!adminOtp.trim()) return;
    setAdminError('');
    setLoading(true);
    try {
      const { getFirebaseAuth } = await import('./firebase');
      const authInstance = await getFirebaseAuth();
      const user = authInstance.currentUser;
      if (!user) {
        throw new Error("Session expired. Please re-authenticate via Email/Password.");
      }
      
      const idToken = await user.getIdToken();
      
      // Verify TOTP code
      const res = await fetch(`${API_BASE}/api/admin/firebase-totp-verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: idToken, otp: adminOtp.trim() })
      });
      
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Invalid TOTP code.');
      }
      
      const data = await res.json();
      setAdminAuthenticated(true);
      localStorage.setItem('supremeai_admin_token', data.token);
      setOtpRequired(false);
      setTotpSetupRequired(false);
      setAdminOtp('');
      fetchAdminData(data.token);
    } catch (err: any) {
      setAdminError(err.message || 'OTP verification failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleAdminLogout = async () => {
    try {
      const { getFirebaseAuth } = await import('./firebase');
      const authInstance = await getFirebaseAuth();
      await authInstance.signOut();
    } catch (e) {
      // ignore logout errors
    }
    localStorage.removeItem('supremeai_admin_token');
    setAdminAuthenticated(false);
    setAdminPassword('');
    setAdminEmail('');
    setOtpRequired(false);
    setTotpSetupRequired(false);
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
    
    const newUserMessage: ChatMessage = { id: Date.now().toString(), sender: 'user', text: userMsg, timestamp: 'Just now' };
    const updatedMessages = [...customerMessages, newUserMessage];
    setCustomerMessages(updatedMessages);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/task/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: userMsg,
          task_type: 'general',
          session_id: sessionId,
          messages: updatedMessages.map(m => ({
            role: m.sender === 'user' ? 'user' : 'assistant',
            content: m.text
          }))
        })
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
    
    const newUserMessage: ChatMessage = { id: Date.now().toString(), sender: 'user', text: userMsg, timestamp: 'Just now' };
    const updatedMessages = [...adminMessages, newUserMessage];
    setAdminMessages(updatedMessages);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/task/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: userMsg,
          task_type: 'general',
          session_id: sessionId,
          messages: updatedMessages.map(m => ({
            role: m.sender === 'user' ? 'user' : 'assistant',
            content: m.text
          }))
        })
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
    <div className="h-screen w-screen flex flex-col bg-[var(--background)] text-[var(--foreground)] overflow-hidden font-sans">

      <Header />

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
          theme={theme}
          toggleTheme={toggleTheme}
        />
      )}

      {/* --- ADMIN GOD LAYER VIEW --- */}
      {currentTab === 'admin' && (
        <AdminConsole
          adminAuthenticated={adminAuthenticated}
          adminPassword={adminPassword}
          setAdminPassword={setAdminPassword}
          adminEmail={adminEmail}
          setAdminEmail={setAdminEmail}
          totpSetupRequired={totpSetupRequired}
          totpSecret={totpSecret}
          provisioningUri={provisioningUri}
          handleAdminLogin={handleAdminLogin}
          handleAdminOtpVerify={handleAdminOtpVerify}
          handleAdminLogout={handleAdminLogout}
          adminError={adminError}
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
          theme={theme}
          toggleTheme={toggleTheme}
        />
      )}

      {/* Embedded Status Bar */}
      <div className="h-6 flex-shrink-0 bg-[var(--sidebar-bg)] border-t border-[var(--border-color)] flex items-center px-4 text-[10px] font-mono text-slate-400 justify-between">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${serverOnline ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}></span>
            Agent Server Status: {serverOnline ? 'Online' : 'Offline'}
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
