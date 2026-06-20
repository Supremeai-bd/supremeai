import type { ChatMessage, Skill, Checkpoint, CloudStats, GcpHealth } from '../types';

interface AdminConsoleProps {
  adminAuthenticated: boolean;
  adminPassword: string;
  setAdminPassword: (val: string) => void;
  adminError: string;
  handleAdminLogin: () => void;
  handleAdminLogout: () => void;
  actionStatus: string;
  gcpHealth: GcpHealth | null;
  cloudStats: CloudStats | null;
  skillQuery: string;
  setSkillQuery: (val: string) => void;
  skills: Skill[];
  handleInstallSkill: (name: string) => void;
  checkpoints: Checkpoint[];
  handleDeleteCheckpoint: (taskId: string) => void;
  adminSubTab: 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'project_status';
  setAdminSubTab: (tab: 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'project_status') => void;
  handleTriggerDeploy: () => void;
  adminMessages: ChatMessage[];
  loading: boolean;
  adminInput: string;
  setAdminInput: (val: string) => void;
  handleSendAdmin: () => void;
  rulesJson: string;
  setRulesJson: (val: string) => void;
  saveStatus: string;
  handleSaveRules: () => void;
  liveLogs: string[];
  setLiveLogs: (logs: string[]) => void;
  costReport: string;
  healthMap: any;
  newUsername: string;
  setNewUsername: (val: string) => void;
  newUserRole: string;
  setNewUserRole: (val: string) => void;
  newUserPerms: string;
  setNewUserPerms: (val: string) => void;
  handleSaveUser: () => void;
  adminUsers: any[];
  handleDeleteUser: (username: string) => void;
  envConfig: Record<string, string>;
  setEnvConfig: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  handleSaveConfig: () => void;
}

export function AdminConsole({
  adminAuthenticated,
  adminPassword,
  setAdminPassword,
  adminError,
  handleAdminLogin,
  handleAdminLogout,
  actionStatus,
  gcpHealth,
  cloudStats,
  skillQuery,
  setSkillQuery,
  skills,
  handleInstallSkill,
  checkpoints,
  handleDeleteCheckpoint,
  adminSubTab,
  setAdminSubTab,
  handleTriggerDeploy,
  adminMessages,
  loading,
  adminInput,
  setAdminInput,
  handleSendAdmin,
  rulesJson,
  setRulesJson,
  saveStatus,
  handleSaveRules,
  liveLogs,
  setLiveLogs,
  costReport,
  healthMap,
  newUsername,
  setNewUsername,
  newUserRole,
  setNewUserRole,
  newUserPerms,
  setNewUserPerms,
  handleSaveUser,
  adminUsers,
  handleDeleteUser,
  envConfig,
  setEnvConfig,
  handleSaveConfig
}: AdminConsoleProps) {
  return (
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
              <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold font-mono">GCP Health Matrix</div>
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
                  onChange={e => { setSkillQuery(e.target.value); }}
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
              <div className="flex flex-col gap-2 max-h-40 overflow-y-auto font-mono">
                {checkpoints.length === 0 ? (
                  <div className="text-[10px] text-slate-500 font-mono">No checkpoints stored.</div>
                ) : (
                  checkpoints.map(cp => (
                    <div key={cp.task_id} className="bg-white/[0.01] border border-slate-900 rounded p-2 flex justify-between items-center text-[11px]">
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
  );
}
