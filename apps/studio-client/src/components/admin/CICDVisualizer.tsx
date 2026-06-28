import { Card, Badge } from '../ui';
import { GitBranch, Play, RotateCcw, FlaskConical, CheckCircle2, AlertTriangle, Clock, User, Terminal, ChevronDown, ChevronUp } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useStore } from '../../store/useStore';
import { useCIReports } from '../../hooks/useAdminApi';
import type { CIReport } from '../../types';

interface FeatureFlag {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  rollout: number;
  environment: 'staging' | 'production';
}

const MOCK_FLAGS: FeatureFlag[] = [
  { id: '1', name: 'new_chat_ui', description: 'New chat interface with streaming', enabled: true, rollout: 25, environment: 'production' },
  { id: '2', name: 'rag_v2', description: 'Improved RAG retrieval algorithm', enabled: false, rollout: 0, environment: 'staging' },
  { id: '3', name: 'dark_mode', description: 'Dark mode toggle for all users', enabled: true, rollout: 100, environment: 'production' },
];

export function CICDVisualizer() {
  const [flags, setFlags] = useState<FeatureFlag[]>(MOCK_FLAGS);
  const [selectedRun, setSelectedRun] = useState<CIReport | null>(null);
  const { deployGate, fetchGateStatus } = useStore();
  const { data: ciReports, isLoading: isCILoading, refetch: refetchCI } = useCIReports(15);

  useEffect(() => {
    fetchGateStatus();
  }, []);

  const toggleFlag = (id: string) => {
    setFlags(flags.map(f => (f.id === id ? { ...f, enabled: !f.enabled } : f)));
  };

  const updateRollout = (id: string, rollout: number) => {
    setFlags(flags.map(f => (f.id === id ? { ...f, rollout } : f)));
  };

  const getStatusBadgeVariant = (status: string): 'success' | 'warning' | 'info' | 'danger' => {
    const s = status.toLowerCase();
    if (s === 'success') return 'success';
    if (s === 'failure' || s === 'failed') return 'danger';
    if (s === 'running' || s === 'in_progress') return 'warning';
    return 'info';
  };

  const handleDeploy = async () => {
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || '';
      const res = await fetch(`${API_BASE}/admin-api/deploy`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('supremeai_admin_token') || 'supreme-god-password'}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        alert(`✅ ${data.message || 'Deployment triggered successfully!'}`);
      } else {
        alert('❌ Deployment failed (unauthorized or server error).');
      }
    } catch (e: any) {
      alert(`❌ Deployment failed: ${e.message}`);
    }
  };

  const formatRuntime = (secs: number) => {
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return `${mins}m ${rem}s`;
  };

  return (
    <div className="flex-grow p-6 overflow-y-auto bg-[#030611]">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00f3ff]/15">
        <h2 className="text-lg font-bold font-['Space_Grotesk'] tracking-widest text-[#00f3ff] uppercase">
          🚀 CI/CD & Deployment Control
        </h2>
        <div className="flex gap-2">
          <button 
            onClick={() => refetchCI()}
            className="flex items-center gap-2 px-3 py-1.5 rounded border border-slate-800 text-slate-400 hover:text-white text-[10px] font-bold font-mono uppercase transition-colors"
          >
            <RotateCcw size={10} /> Refresh
          </button>
          <button
            onClick={handleDeploy}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-[#00f3ff] text-black text-[10px] font-bold font-mono uppercase hover:bg-cyan-400 transition-colors"
          >
            <Play size={10} /> Deploy
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Dynamic Pipelines History Card (Takes 2 columns on lg screen) */}
        <div className="lg:col-span-2">
          <Card title="CI Webhook Pipeline History" icon={<GitBranch size={14} />}>
            {isCILoading ? (
              <div className="text-center py-8 text-slate-500 font-mono text-[10px]">Loading CI run history...</div>
            ) : !ciReports || ciReports.length === 0 ? (
              <div className="text-center py-8 text-slate-500 font-mono text-[10px]">No GHA workflow runs recorded yet.</div>
            ) : (
              <div className="flex flex-col gap-3">
                {ciReports.map((report) => (
                  <div 
                    key={report.id} 
                    onClick={() => setSelectedRun(selectedRun?.id === report.id ? null : report)}
                    className={`p-3 rounded-lg border transition-all cursor-pointer ${
                      selectedRun?.id === report.id 
                        ? 'border-[#00f3ff] bg-[#00f3ff]/5' 
                        : 'border-slate-800 bg-slate-900/20 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className={`w-2 h-2 rounded-full ${
                          report.status.toLowerCase() === 'success' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' :
                          report.status.toLowerCase() === 'failure' || report.status.toLowerCase() === 'failed' ? 'bg-rose-500 shadow-[0_0_8px_#f43f5e]' :
                          'bg-amber-500 shadow-[0_0_8px_#f59e0b] animate-pulse'
                        }`} />
                        <div>
                          <div className="text-xs font-bold text-white font-mono">
                            Run #{report.run_number} — {report.workflow_name}
                          </div>
                          <div className="flex items-center gap-3 text-[10px] text-slate-500 mt-1 font-mono">
                            <span className="flex items-center gap-1"><GitBranch size={10} /> {report.branch}</span>
                            <span className="flex items-center gap-1"><Clock size={10} /> {formatRuntime(report.runtime_seconds)}</span>
                            <span className="flex items-center gap-1"><User size={10} /> {report.actor}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={getStatusBadgeVariant(report.status)}>{report.status.toUpperCase()}</Badge>
                        {selectedRun?.id === report.id ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
                      </div>
                    </div>

                    {/* Detailed Accordion Content when selected */}
                    {selectedRun?.id === report.id && (
                      <div className="mt-4 pt-3 border-t border-slate-800 text-[10px] font-mono leading-relaxed text-slate-300">
                        <div className="grid grid-cols-2 gap-2 mb-3 text-slate-400">
                          <div>Commit: <span className="text-white">{report.commit_sha.substring(0, 7)}</span></div>
                          <div>Event: <span className="text-white">{report.event_name.toUpperCase()}</span></div>
                          <div>Run ID: <span className="text-white">{report.run_id}</span></div>
                          <div>Recorded: <span className="text-white">{new Date(report.created_at * 1000).toLocaleString()}</span></div>
                        </div>

                        {/* Jobs Summary Details */}
                        {report.jobs_summary && Object.keys(report.jobs_summary).length > 0 && (
                          <div className="mb-3">
                            <div className="text-slate-400 mb-1 font-bold">Jobs Summary:</div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                              {Object.entries(report.jobs_summary).map(([job, info]: [string, any]) => (
                                <div key={job} className="flex justify-between items-center p-1.5 rounded bg-slate-950 border border-slate-900">
                                  <span className="text-[9px] truncate max-w-[150px]">{job}</span>
                                  <Badge variant={getStatusBadgeVariant(info.status || 'info')}>{String(info.status).toUpperCase()}</Badge>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Error logs output if exists */}
                        {report.error_logs && (
                          <div className="mt-2">
                            <div className="flex items-center gap-1.5 text-rose-400 mb-1 font-bold">
                              <Terminal size={10} /> Error Logs / Diagnostics:
                            </div>
                            <pre className="p-2.5 rounded bg-slate-950 border border-rose-950/30 text-rose-300 text-[9px] max-h-40 overflow-y-auto whitespace-pre-wrap font-mono">
                              {report.error_logs}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Feature Flags Column */}
        <div>
          <Card title="Feature Flags" icon={<FlaskConical size={14} />}>
            <div className="flex flex-col gap-3">
              {flags.map(flag => (
                <div key={flag.id} className="p-3 rounded-lg border border-slate-800 bg-slate-900/30">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="text-xs font-bold text-white font-mono">{flag.name}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">{flag.description}</div>
                    </div>
                    <button
                      onClick={() => toggleFlag(flag.id)}
                      className={`w-8 h-4 rounded-full transition-colors ${flag.enabled ? 'bg-[#00f3ff]' : 'bg-slate-700'}`}
                    >
                      <div className={`w-3 h-3 rounded-full bg-white transition-transform ${flag.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
                    </button>
                  </div>
                  {flag.enabled && (
                    <div className="mt-2">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-slate-400">Rollout</span>
                        <span className="text-[10px] text-white font-mono">{flag.rollout}%</span>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-1">
                        <div className="h-full rounded-full bg-[#00f3ff]" style={{ width: `${flag.rollout}%` }} />
                      </div>
                      <div className="flex gap-1 mt-2">
                        <button onClick={() => updateRollout(flag.id, Math.max(0, flag.rollout - 10))} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-white">-10%</button>
                        <button onClick={() => updateRollout(flag.id, Math.min(100, flag.rollout + 10))} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 hover:text-white">+10%</button>
                      </div>
                    </div>
                  )}
                  <div className="mt-2">
                    <Badge variant={flag.environment === 'production' ? 'success' : 'info'}>{flag.environment}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
