import type { ChatMessage, Skill, Checkpoint, CloudStats, GcpHealth } from '../types';
import { CommandCenter, LiveLogs, CostAuditor, HealthMap, UserManager, ConfigEditor, ModelRouter, EnhancedSkillMarketplace, MemoryBrowser, CloudOrchestrator, ObservabilityDashboard, ThreatDetection, VisualRulesBuilder, CICDVisualizer, GithubIntegration, BackupRestore } from './admin';

interface AdminConsoleProps {
  adminAuthenticated: boolean;
  adminPassword: string;
  setAdminPassword: (val: string) => void;
  adminEmail: string;
  setAdminEmail: (val: string) => void;
  totpSetupRequired: boolean;
  totpSecret: string;
  provisioningUri: string;
  adminError: string;
  handleAdminLogin: () => void;
  handleAdminOtpVerify: () => void;
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
  adminSubTab: 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'command-center' | 'model-router' | 'skills' | 'memory' | 'cloud' | 'observability' | 'threats' | 'rules' | 'cicd' | 'github' | 'backups';
  setAdminSubTab: (tab: 'sandbox' | 'logs' | 'costs' | 'health' | 'users' | 'config' | 'command-center' | 'model-router' | 'skills' | 'memory' | 'cloud' | 'observability' | 'threats' | 'rules' | 'cicd' | 'github' | 'backups') => void;
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
  otpRequired: boolean;
  adminOtp: string;
  setAdminOtp: (val: string) => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

export function AdminConsole({
  adminAuthenticated,
  adminPassword,
  setAdminPassword,
  adminEmail,
  setAdminEmail,
  totpSetupRequired,
  totpSecret,
  provisioningUri,
  adminError,
  handleAdminLogin,
  handleAdminOtpVerify,
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
  handleSaveConfig,
  otpRequired,
  adminOtp,
  setAdminOtp,
  theme,
  toggleTheme
}: AdminConsoleProps) {
  return (
    <div className="flex-grow flex flex-col overflow-hidden bg-[#030407]">
      {!adminAuthenticated ? (
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
            {!otpRequired ? (
              // --- First Factor: Firebase Auth Email/Password Sign-In ---
              // Added by Agent Antigravity on 2026-06-21 to allow admin role users to authenticate.
              <div className="flex flex-col gap-3.5">
                <input
                  type="email"
                  placeholder="Enter Admin Email..."
                  value={adminEmail}
                  onChange={e => setAdminEmail(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAdminLogin()}
                  className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono"
                />
                <input
                  type="password"
                  placeholder="Enter Admin Password..."
                  value={adminPassword}
                  onChange={e => setAdminPassword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAdminLogin()}
                  className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono"
                />
                {adminError && <div className="text-[#ff4d4f] text-xs mt-1 font-mono">{adminError}</div>}
              </div>
            ) : (
              // --- Second Factor: Personalized TOTP Verification (and Setup if required) ---
              // Added by Agent Antigravity on 2026-06-21 to handle unique MFA keys.
              <div className="flex flex-col gap-4 items-center">
                {totpSetupRequired && provisioningUri && (
                  <div className="flex flex-col items-center gap-2.5 p-3.5 bg-cyan-950/20 border border-cyan-800/20 rounded-xl max-w-xs">
                    <div className="text-[11px] text-[#00f3ff] font-bold font-mono">Scan this QR Code in Authenticator:</div>
                    <img 
                      src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(provisioningUri)}`} 
                      alt="Google Authenticator QR Code"
                      className="border-2 border-[#00f3ff] rounded-lg bg-white p-1"
                    />
                    <div className="text-[10px] text-slate-400 font-mono text-center">
                      Or enter manual key: <br />
                      <span className="text-white font-bold select-all">{totpSecret}</span>
                    </div>
                  </div>
                )}
                <input
                  type="text"
                  placeholder="Enter 6-digit OTP Code..."
                  value={adminOtp}
                  onChange={e => setAdminOtp(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAdminOtpVerify()}
                  className="w-full text-center bg-[#07090f] border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#00f3ff] transition-all font-mono tracking-widest text-lg"
                  maxLength={6}
                />
                {adminError && <div className="text-[#ff4d4f] text-xs mt-1 font-mono">{adminError}</div>}
                <div className="text-[10px] text-slate-500 font-mono text-center">
                  {!totpSetupRequired ? "Enter the 6-digit code from your Google Authenticator app." : "Confirm code to activate and authorize your account."}
                </div>
              </div>
            )}
            <button
              onClick={otpRequired ? handleAdminOtpVerify : handleAdminLogin}
              className="cyber-button w-full uppercase py-3 text-xs tracking-wider font-mono font-bold"
            >
              {otpRequired ? "Verify OTP & Authorize" : "Sign In & Continue"}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-row overflow-hidden">
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

             {actionStatus && (
               <div className="mb-4 p-2.5 bg-cyan-950/30 border border-cyan-800/40 rounded text-[11px] font-mono text-[#00f3ff]">
                 {actionStatus}
               </div>
             )}
             <div className="flex items-center gap-2">
               <button
                 onClick={toggleTheme}
                 className="text-xs font-bold text-[#00f3ff] hover:text-cyan-400 tracking-wider transition-colors"
               >
                 {theme === 'dark' ? '🌙 Light Mode' : '☀️ Dark Mode'}
               </button>
             </div>
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

          <div className="flex-1 flex flex-col min-w-0">
            <div className="h-10 bg-[#090b11] border-b border-slate-800 flex items-center justify-between px-4">
              <div className="flex gap-2">
                <button
                  onClick={() => setAdminSubTab('command-center')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'command-center' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Command Center
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
                <button
                  onClick={() => setAdminSubTab('model-router')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'model-router' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Model Router
                </button>
                <button
                  onClick={() => setAdminSubTab('skills')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'skills' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Skills
                </button>
                <button
                  onClick={() => setAdminSubTab('memory')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'memory' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Memory
                </button>
                <button
                  onClick={() => setAdminSubTab('cloud')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'cloud' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Cloud
                </button>
                <button
                  onClick={() => setAdminSubTab('observability')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'observability' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Observability
                </button>
                <button
                  onClick={() => setAdminSubTab('threats')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'threats' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Threats
                </button>
                <button
                  onClick={() => setAdminSubTab('rules')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'rules' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Rules
                </button>
                <button
                  onClick={() => setAdminSubTab('cicd')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'cicd' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  CI/CD
                </button>
                <button
                  onClick={() => setAdminSubTab('github')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'github' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  GitHub
                </button>
                <button
                  onClick={() => setAdminSubTab('backups')}
                  className={`px-3 py-1 text-xs font-semibold rounded font-mono transition-colors ${adminSubTab === 'backups' ? 'bg-[#00f3ff]/20 text-[#00f3ff]' : 'text-slate-400 hover:text-white'}`}
                >
                  Backups
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
            {adminSubTab === 'command-center' && (
              <CommandCenter />
            )}

            {adminSubTab === 'sandbox' && (
              <div className="flex-grow flex flex-row overflow-hidden">
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
              <LiveLogs liveLogs={liveLogs} setLiveLogs={setLiveLogs} />
            )}

            {adminSubTab === 'costs' && (
              <CostAuditor costReport={costReport} />
            )}

            {adminSubTab === 'health' && (
              <HealthMap healthMap={healthMap} />
            )}

            {adminSubTab === 'users' && (
              <UserManager
                newUsername={newUsername}
                setNewUsername={setNewUsername}
                newUserRole={newUserRole}
                setNewUserRole={setNewUserRole}
                newUserPerms={newUserPerms}
                setNewUserPerms={setNewUserPerms}
                handleSaveUser={handleSaveUser}
                adminUsers={adminUsers}
                handleDeleteUser={handleDeleteUser}
              />
            )}

            {adminSubTab === 'config' && (
              <ConfigEditor
                envConfig={envConfig}
                setEnvConfig={setEnvConfig}
                handleSaveConfig={handleSaveConfig}
              />
            )}

            {adminSubTab === 'model-router' && <ModelRouter />}

            {adminSubTab === 'skills' && <EnhancedSkillMarketplace />}
            {adminSubTab === 'memory' && <MemoryBrowser />}
            {adminSubTab === 'cloud' && <CloudOrchestrator />}
            {adminSubTab === 'observability' && <ObservabilityDashboard />}
            {adminSubTab === 'threats' && <ThreatDetection />}
            {adminSubTab === 'rules' && <VisualRulesBuilder />}
            {adminSubTab === 'cicd' && <CICDVisualizer />}
            {adminSubTab === 'github' && <GithubIntegration />}
            {adminSubTab === 'backups' && <BackupRestore />}
          </div>
        </div>
      )}
    </div>
  );
}
